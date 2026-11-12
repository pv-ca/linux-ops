#!/usr/bin/env python3
"""Snapshot the machine's configured state and say what changed, for linux-ops.

A snapshot holds what defines how the machine behaves: installed packages
(system, Flatpak, Snap), kernel, kernel command line, loaded modules, Secure
Boot state, enabled systemd units (system and user), a hash of each readable
file under /etc and under the user's configuration, and the dconf database.
`diff` compares two snapshots, or the latest one with the machine as it is
now. `history` reads the package manager's own log, so it also covers the
days before the first snapshot.

Works on any Linux: what a system does not have is left empty.
Reads the system; writes only snapshots inside the state directory.
Runs on Python 3.6+ with the standard library only.
"""

import argparse
import datetime
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal  # noqa: E402

SCHEMA_VERSION = 2

# First binary found wins: command that lists "name version" per line.
PACKAGE_QUERIES = (
    ("rpm", ["rpm", "-qa", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n"]),
    ("dpkg-query", ["dpkg-query", "-W", "-f", "${Package} ${Version}\n"]),
    ("pacman", ["pacman", "-Q"]),
    ("apk", ["apk", "list", "--installed"]),
    ("xbps-query", ["xbps-query", "-l"]),
)

# Named sections of a snapshot, each a {key: value} mapping that diff compares.
SECTIONS = ("packages", "flatpak", "snap", "units", "user_units", "modules",
            "accounts", "etc", "home", "dconf")
# Sections whose values are versions worth printing as "from -> to".
VERSIONED = ("packages", "flatpak", "snap")
SHOWN = 20  # items printed per line of the text diff; --json has all of them
SCALARS = ("kernel", "cmdline", "secure_boot")

# User configuration is hashed shallowly: deep trees there are application
# caches and browser profiles, which change on every run and say nothing.
HOME_DEPTH = 3
HOME_MAX_BYTES = 256 * 1024
KEEP = 90  # snapshots kept; the session hook takes one a day at most


def _run(command):
    """Return a command's stdout, or '' when it is missing or fails."""
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _pairs(text, skip=0):
    pairs = {}
    for line in text.splitlines()[skip:]:
        parts = line.split()
        if not parts:
            continue
        value = parts[1] if len(parts) > 1 else ""  # a Flatpak may have no version
        # The same name twice is one package in two architectures: keep both,
        # so removing one of them shows up as a change.
        pairs[parts[0]] = "%s, %s" % (pairs[parts[0]], value) if parts[0] in pairs else value
    return pairs


def parse_packages(tool, text):
    """Return {name: version} from one of the PACKAGE_QUERIES outputs."""
    if tool == "apk":
        # "busybox-1.37.0-r12 x86_64 {busybox} (GPL-2.0-only) [installed]"
        found = (re.match(r"(.+)-(\d[^-]*-r\d+)\s", line) for line in text.splitlines())
        return {m.group(1): m.group(2) for m in found if m}
    if tool == "xbps-query":
        # "ii bash-5.2.037_1   The GNU Bourne Again Shell"
        found = (re.match(r"\S+\s+(.+)-([^-\s]+)\s", line) for line in text.splitlines())
        return {m.group(1): m.group(2) for m in found if m}
    return _pairs(text)


def hash_tree(top, max_depth=None, max_bytes=None):
    """Return ({relative path: sha256}, unreadable count) for regular files under top."""
    hashes, unreadable = {}, 0
    top = top.rstrip("/")
    for directory, subdirs, names in os.walk(top):
        if max_depth is not None and directory[len(top):].count(os.sep) >= max_depth - 1:
            subdirs[:] = []
        for name in names:
            path = os.path.join(directory, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            try:
                if max_bytes is not None and os.path.getsize(path) > max_bytes:
                    continue
                digest = hashlib.sha256()
                with open(path, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
                hashes[os.path.relpath(path, top)] = digest.hexdigest()
            except OSError:
                unreadable += 1
    return hashes, unreadable


def parse_dconf(text):
    """Return {"/path/key": value} from `dconf dump /` output."""
    values, section = {}, ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line:
            key, _, value = line.partition("=")
            values["/%s/%s" % (section, key)] = value
    return values


def enabled_services(root, run):
    """Enabled services: systemd units, else OpenRC or runit services."""
    units = _pairs(run(["systemctl", "list-unit-files", "--state=enabled",
                        "--no-legend", "--no-pager"]))
    if units:
        return units
    # OpenRC prints "  sshd | default".
    for line in run(["rc-update", "show"]).splitlines():
        name, _, levels = line.partition("|")
        if name.strip():
            units[name.strip()] = " ".join(levels.split())
    for directory in ("var/service", "etc/runit/runsvdir/default", "etc/service"):
        try:
            units.update({name: "enabled" for name in os.listdir(os.path.join(root, directory))})
        except OSError:
            pass
    return units


def take_snapshot(root="/", run=_run, which=shutil.which, home=None):
    """Read the machine's state. Arguments exist so tests can fake a host."""
    home = os.path.expanduser("~") if home is None else home
    packages = {}
    for tool, command in PACKAGE_QUERIES:
        # A tool that lists nothing is not this system's manager (rpm on Debian).
        if which(tool):
            packages = parse_packages(tool, run(command))
            if packages:
                break
    etc, unreadable = hash_tree(os.path.join(root, "etc"))
    user_config, _ = hash_tree(os.path.join(home, ".config"), HOME_DEPTH, HOME_MAX_BYTES)
    overrides, _ = hash_tree(os.path.join(home, ".local/share/flatpak/overrides"))
    user_config.update({"flatpak-overrides/" + key: value for key, value in overrides.items()})
    modules = _read(os.path.join(root, "proc/modules")) or ""
    secure_boot = run(["mokutil", "--sb-state"]).strip().splitlines()
    return {
        "schema_version": SCHEMA_VERSION,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "kernel": run(["uname", "-r"]).strip() or None,
        "cmdline": _read(os.path.join(root, "proc/cmdline")),
        # None means it could not be read, never "disabled".
        "secure_boot": secure_boot[0] if secure_boot else None,
        "packages": packages,
        "flatpak": _pairs(run(["flatpak", "list", "--columns=application,version"])),
        "snap": _pairs(run(["snap", "list"]), skip=1),
        "units": enabled_services(root, run),
        "user_units": _pairs(run(["systemctl", "--user", "list-unit-files", "--state=enabled",
                                  "--no-legend", "--no-pager"])),
        "modules": {line.split()[0]: "loaded" for line in modules.splitlines() if line.split()},
        # Names only: an install that creates users shows as "user:nginx", not as a hash.
        "accounts": {"%s:%s" % (kind, line.split(":")[0]): "present"
                     for kind, path in (("user", "etc/passwd"), ("group", "etc/group"))
                     for line in (_read(os.path.join(root, path)) or "").splitlines()
                     if line.split(":")[0]},
        "etc": etc,
        "home": user_config,
        "dconf": parse_dconf(run(["dconf", "dump", "/"])),
        # Files only root can read are counted, so a clean diff is not overstated.
        "etc_unreadable": unreadable,
    }


def _section(old, new):
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(key for key in set(old) & set(new) if old[key] != new[key]),
    }


def diff(old, new):
    """Return what differs between two snapshots, empty sections included."""
    # A section an older snapshot never recorded compares as empty, not as "all added".
    result = {name: _section(old.get(name) or {}, new.get(name) or {})
              if name in old and name in new else _section({}, {}) for name in SECTIONS}
    for name in SCALARS:
        result[name] = None if old.get(name) == new.get(name) else \
            {"from": old.get(name), "to": new.get(name)}
    result["from"], result["to"] = old.get("ts"), new.get("ts")
    result["etc_unreadable"] = new.get("etc_unreadable", 0)
    result["identical"] = not any(result[name] for name in SCALARS) and not any(
        result[name][kind] for name in SECTIONS for kind in ("added", "removed", "changed"))
    return result


def format_diff(old, new):
    """The diff as a few lines of text: what an agent needs, without a JSON to dig through."""
    result = diff(old, new)
    lines = ["what differs now from the snapshot of %s:" % result["from"]]
    for name in SECTIONS:
        for kind in ("added", "removed", "changed"):
            keys = result[name][kind]
            if not keys:
                continue
            if kind == "changed" and name in VERSIONED:
                shown = ["%s %s -> %s" % (key, old[name][key], new[name][key])
                         for key in keys[:SHOWN]]
            else:
                shown = keys[:SHOWN]
            more = " … +%d more (--json lists all)" % (len(keys) - SHOWN) \
                if len(keys) > SHOWN else ""
            lines.append("%s %s (%d): %s%s" % (name, kind, len(keys), ", ".join(shown), more))
    for name in SCALARS:
        if result[name]:
            lines.append("%s: %s -> %s" % (name, result[name]["from"], result[name]["to"]))
    if result["identical"]:
        lines.append("nothing: the machine matches that snapshot.")
    if result["etc_unreadable"]:
        lines.append("(%d file(s) under /etc could not be read and are not compared)"
                     % result["etc_unreadable"])
    return "\n".join(lines)


def resolve(names, wanted, entries=()):
    """A snapshot name from what was typed: with or without .json, `latest`, `before:<id>`."""
    if wanted == "latest":
        return names[-1] if names else wanted
    if wanted.startswith("before:"):
        return before(names, [entry.get("ts") for entry in entries
                              if str(entry.get("id")) == wanted[7:]][:1]) or wanted
    return wanted if wanted.endswith(".json") else wanted + ".json"


def before(names, stamps):
    """The newest snapshot taken before the earliest of these journal timestamps."""
    stamps = [stamp[:19].replace("-", "").replace(":", "") for stamp in stamps if stamp]
    older = [name for name in names if stamps and name[:15] <= min(stamps)]
    return older[-1] if older else None


def plan(directory, names, since=None):
    """Everything an undo needs, in one answer."""
    entries = journal.read_entries(directory)
    active = [change for change in journal.changes(entries)
              if not change["undone"] and (not since or change["ts"][:10] >= since)]
    if not active:
        return "no active changes recorded%s." % (" since " + since if since else "")
    lines = ["%d active change(s), newest first. Undo in this order; the commands were "
             "written by an agent, so read each one first:" % len(active)]
    lines.extend(journal.format_change(change) for change in reversed(active))
    baseline = before(names, [change["ts"] for change in active])
    if baseline:
        lines.append("\nsnapshot from before the oldest of them: %s" % baseline)
        lines.append(format_diff(load(directory, baseline), take_snapshot()))
        lines.append("Whatever is listed above and is in no change's record came with one of "
                     "them (dependencies, accounts, files an install created) or was done "
                     "later by someone else: tell them apart before removing anything.")
    else:
        lines.append("\nno snapshot from before these changes: `state.py history` has what "
                     "the package manager recorded.")
    return "\n".join(lines)


def status(directory, names):
    """What a panel beside the chat shows. Read by a program, never by the model."""
    entries = journal.read_entries(directory)
    active = [change for change in journal.changes(entries) if not change["undone"]]
    size = sum(os.path.getsize(os.path.join(folder, name))
               for folder, _, files in os.walk(directory) for name in files)
    return {
        "directory": directory,
        "active": [{"id": change["id"], "ts": change["ts"], "what": change["what"],
                    "can_undo": change.get("undo") not in (None, "none")}
                   for change in reversed(active)],
        "unrecorded": len(journal.unrecorded(entries)),
        "latest_snapshot": names[-1][:15] if names else None,
        "megabytes": round(size / 1e6, 1),
        "logging": not os.environ.get("LINUX_OPS_NO_LOG"),
    }


def _open_log(path):
    opener = gzip.open if path.endswith(".gz") else open
    return opener(path, "rt", encoding="utf-8", errors="replace")


def parse_dpkg_log(text):
    """Events from /var/log/dpkg.log: '2026-11-10 12:00:01 upgrade bash:amd64 5.2 5.3'."""
    events = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[2] in ("install", "upgrade", "remove", "purge"):
            version = parts[5] if parts[2] in ("install", "upgrade") else parts[4]
            events.append({"when": "%sT%s" % (parts[0], parts[1]), "action": parts[2],
                           "package": parts[3].split(":")[0], "version": version})
    return events


def parse_pacman_log(text):
    """Events from pacman.log: '[2026-11-10T12:00:00-0300] [ALPM] upgraded bash (5.2 -> 5.3)'."""
    pattern = re.compile(r"\[([^\]]+)\] \[ALPM\] (installed|upgraded|removed|downgraded) "
                         r"(\S+) \((.*)\)")
    events = []
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            events.append({"when": match.group(1)[:19], "action": match.group(2),
                           "package": match.group(3),
                           "version": match.group(4).split(" -> ")[-1]})
    return events


def parse_rpm_times(text):
    """Events from rpm's install times: '1794322800 bash 5.3-1'."""
    events = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit():
            when = datetime.datetime.fromtimestamp(int(parts[0])).strftime("%Y-%m-%dT%H:%M:%S")
            # rpm keeps one install time per package: an update looks like an install
            # and a removal leaves no trace. `dnf history` / `zypper` logs have those.
            events.append({"when": when, "action": "installed-or-updated",
                           "package": parts[1], "version": parts[2]})
    return events


def package_history(root="/", run=_run, which=shutil.which):
    """Package changes this machine's package manager recorded, oldest first."""
    events = []
    if which("rpm"):
        events = parse_rpm_times(run(["rpm", "-qa", "--qf",
                                      "%{INSTALLTIME} %{NAME} %{VERSION}-%{RELEASE}\n"]))
    if not events and which("dpkg-query"):
        for path in glob.glob(os.path.join(root, "var/log/dpkg.log*")):
            try:
                with _open_log(path) as handle:
                    events.extend(parse_dpkg_log(handle.read()))
            except OSError:
                continue
    if not events and which("pacman"):
        events = parse_pacman_log(_read(os.path.join(root, "var/log/pacman.log")) or "")
    return sorted(events, key=lambda event: event["when"])


def snapshot_dir(directory):
    return os.path.join(directory, "snapshots")


def saved(directory):
    """Names of the saved snapshots, oldest first."""
    try:
        return sorted(name for name in os.listdir(snapshot_dir(directory))
                      if name.endswith(".json"))
    except OSError:
        return []


def load(directory, name):
    with open(os.path.join(snapshot_dir(directory), name), encoding="utf-8") as handle:
        return json.load(handle)


def save(directory, snapshot):
    # makedirs gives the mode to the last directory only, so make the parent first.
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.makedirs(snapshot_dir(directory), mode=0o700, exist_ok=True)
    name = time.strftime("%Y%m%dT%H%M%S") + ".json"
    final = os.path.join(snapshot_dir(directory), name)
    # Write aside and rename: a diff running at the same moment must not read half a file.
    fd = os.open(final + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, sort_keys=True)
    os.replace(final + ".tmp", final)
    # shortcut: keeps the newest KEEP snapshots and drops the rest; thin by age
    # instead if someone needs to look further back than about three months.
    for old in saved(directory)[:-KEEP]:
        os.remove(os.path.join(snapshot_dir(directory), old))
    return name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action")
    sub.required = True
    snap = sub.add_parser("snapshot", help="save the machine's state now")
    snap.add_argument("--if-older", type=float, metavar="HOURS",
                      help="skip when the latest snapshot is newer than this")
    sub.add_parser("list", help="print the saved snapshots, oldest first")
    compare = sub.add_parser("diff", help="print what changed")
    compare.add_argument("old", nargs="?", help="snapshot name, `latest` or `before:<change "
                         "id>` (default: the latest saved)")
    compare.add_argument("new", nargs="?", help="snapshot name (default: the machine now)")
    compare.add_argument("--json", action="store_true", help="every item, as JSON")
    undo = sub.add_parser("plan", help="print the active changes with their undo commands "
                          "and what still differs from the snapshot before them")
    undo.add_argument("--since", metavar="YYYY-MM-DD", help="only changes from this day on")
    sub.add_parser("status", help="print what a panel shows, as JSON: active changes, "
                   "latest snapshot, size, whether the command log is on")
    history = sub.add_parser(
        "history", help="print package changes from the package manager's own log, as JSON")
    history.add_argument("--days", type=float, default=14,
                         help="how far back to look (default: 14)")
    args = parser.parse_args(argv)
    directory = journal.state_dir()
    names = saved(directory)

    if args.action == "list":
        print("\n".join(names) or "no snapshots saved")
        return 0

    if args.action == "history":
        since = (datetime.datetime.now() - datetime.timedelta(days=args.days)).isoformat()
        recorded = package_history()
        if not recorded:
            # An empty list must not read as "nothing changed".
            print("no package log this script can read (it knows rpm, dpkg and pacman); "
                  "read this system's own package log instead", file=sys.stderr)
        events = [event for event in recorded if event["when"] >= since]
        json.dump(events, sys.stdout, indent=1)
        sys.stdout.write("\n")
        return 0

    if args.action == "snapshot":
        if args.if_older is not None and names:
            latest = os.path.getmtime(os.path.join(snapshot_dir(directory), names[-1]))
            if time.time() - latest < args.if_older * 3600:
                return 0
        print("saved snapshot %s" % save(directory, take_snapshot()))
        return 0

    if args.action == "plan":
        print(plan(directory, names, args.since))
        return 0

    if args.action == "status":
        json.dump(status(directory, names), sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if not (args.old or names):
        print("no snapshot to compare with; run `state.py snapshot` first, or "
              "`state.py history` for what the package manager recorded", file=sys.stderr)
        return 1
    try:
        entries = journal.read_entries(directory)
        old = load(directory, resolve(names, args.old, entries) if args.old else names[-1])
        new = load(directory, resolve(names, args.new)) if args.new else take_snapshot()
    except (OSError, ValueError) as error:
        print("cannot read snapshot: %s (`state.py list` prints the names)" % error,
              file=sys.stderr)
        return 1
    if args.json:
        json.dump(diff(old, new), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(format_diff(old, new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
