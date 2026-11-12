#!/usr/bin/env python3
"""Profile a Linux host for the linux-ops skill.

Reads the host and prints one JSON object describing the axes the skill
branches on, plus notes on what makes the usual commands wrong there.
Works on any distribution. Changes nothing.
Runs on Python 3.6+ with the standard library only.
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys

SCHEMA_VERSION = 2  # 2: `mode` and `read_only_reasons` gave way to `notes`

# Distributions exercised in CI. Anything else that resolves to one of
# these families through ID_LIKE is a derivative: same axes, no guarantee.
TIER1_IDS = {
    "fedora": "fedora",
    "debian": "debian",
    "ubuntu": "debian",
    "arch": "arch",
    "opensuse-tumbleweed": "suse",
    "opensuse-leap": "suse",
}

# ID_LIKE tokens, most specific first.
FAMILY_BY_LIKE = (
    ("fedora", "fedora"),
    ("rhel", "fedora"),
    ("centos", "fedora"),
    ("ubuntu", "debian"),
    ("debian", "debian"),
    ("arch", "arch"),
    ("opensuse", "suse"),
    ("suse", "suse"),
)

PACKAGE_MANAGER = {
    "fedora": "dnf",
    "debian": "apt",
    "arch": "pacman",
    "suse": "zypper",
}

# The executable that proves the package manager is installed.
PACKAGE_MANAGER_BINARY = {
    "dnf": "dnf",
    "apt": "apt-get",
    "pacman": "pacman",
    "zypper": "zypper",
}

# Outside the four families the manager is whichever of these is installed.
OTHER_MANAGERS = (
    ("apk", "apk"),
    ("xbps", "xbps-install"),
    ("portage", "emerge"),
    ("eopkg", "eopkg"),
    ("swupd", "swupd"),
    ("slackpkg", "slackpkg"),
    ("nix", "nix-env"),
)


def _read(root, relative):
    """Return the stripped text of a file under root, or None."""
    path = os.path.join(root, relative.lstrip("/"))
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _exists(root, relative):
    return os.path.exists(os.path.join(root, relative.lstrip("/")))


def parse_os_release(text):
    """Parse os-release syntax (shell-style KEY=value) into a dict."""
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        try:
            # Joined, so an unquoted value with a space is not cut at the space.
            value = " ".join(shlex.split(raw))
        except ValueError:
            value = raw.strip("\"'")
        fields[key.strip()] = value
    return fields


def detect_os(root):
    text = _read(root, "/etc/os-release") or _read(root, "/usr/lib/os-release")
    fields = parse_os_release(text) if text else {}
    return {
        "id": fields.get("ID", "").lower() or None,
        "id_like": fields.get("ID_LIKE", "").lower().split(),
        "version_id": fields.get("VERSION_ID") or None,
        "variant_id": fields.get("VARIANT_ID", "").lower() or None,
        "pretty_name": fields.get("PRETTY_NAME") or None,
    }


def detect_family(os_info):
    """Return (family, support) where support is tier1, derivative or untested."""
    os_id = os_info["id"]
    if os_id in TIER1_IDS:
        return TIER1_IDS[os_id], "tier1"
    tokens = ([os_id] if os_id else []) + os_info["id_like"]
    for token, family in FAMILY_BY_LIKE:
        for candidate in tokens:
            if candidate == token or candidate.startswith(token + "-"):
                return family, "derivative"
    return None, "untested"


def _root_is_read_only(root):
    mounts = _read(root, "/proc/mounts")
    if not mounts:
        return False
    read_only = False
    # Later entries shadow earlier ones for the same mount point.
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] == "/":
            read_only = "ro" in parts[3].split(",")
    return read_only


def detect_change_model(root, which):
    """Return how persistent system changes are made on this host."""
    if _exists(root, "/etc/NIXOS"):
        return "declarative"
    if _exists(root, "/run/ostree-booted"):
        return "image"
    if which("transactional-update") and _root_is_read_only(root):
        return "image"
    return "imperative"


SERVICE_MANAGERS = ("init", "openrc-init", "runit", "runit-init", "s6-svscan", "dinit")


def detect_init(root):
    if _exists(root, "/run/systemd/system"):
        return "systemd"
    name = _read(root, "/proc/1/comm")
    # A container's first process is often sleep, a shell or a tiny reaper: nothing there
    # manages services, and calling it "the init" sends the agent to commands that do not exist.
    in_container = _exists(root, "/run/.containerenv") or _exists(root, "/.dockerenv")
    if in_container and name not in SERVICE_MANAGERS:
        return "none"
    return name or None


def detect_mac(root):
    """Return the mandatory access control system and its state."""
    enforce = _read(root, "/sys/fs/selinux/enforce")
    if enforce is not None:
        return {"system": "selinux", "state": "enforcing" if enforce == "1" else "permissive"}
    if _read(root, "/sys/module/apparmor/parameters/enabled") == "Y":
        return {"system": "apparmor", "state": "enabled"}
    return {"system": None, "state": None}


def detect_session(env):
    kind = (env.get("XDG_SESSION_TYPE") or "").lower()
    if kind not in ("wayland", "x11"):
        if env.get("WAYLAND_DISPLAY"):
            kind = "wayland"
        elif env.get("DISPLAY"):
            kind = "x11"
        else:
            kind = "none"
    return {"type": kind, "desktop": env.get("XDG_CURRENT_DESKTOP") or None}


def _systemd_detect_virt(which, flag):
    """Run systemd-detect-virt with --vm or --container; None when unavailable."""
    if not which("systemd-detect-virt"):
        return None
    try:
        result = subprocess.run(
            ["systemd-detect-virt", flag],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def classify_virtualization(container, vm):
    """Map systemd-detect-virt answers to an environment name."""
    if container == "wsl":
        return "wsl"
    # container-other is a confinement systemd cannot name, which is what an
    # agent's command sandbox looks like from the inside.
    if container == "container-other":
        return "sandbox"
    if container not in (None, "none"):
        return "container"
    if vm not in (None, "none"):
        return "vm"
    if container == "none" and vm == "none":
        return "physical"
    return None


def detect_environment(root, env, which, live):
    """Return wsl, container, sandbox, vm, physical or None when undetermined."""
    kernel = (_read(root, "/proc/sys/kernel/osrelease") or "").lower()
    if "microsoft" in kernel or "wsl" in kernel:
        return "wsl"
    if env.get("container") or _exists(root, "/run/.containerenv") or _exists(root, "/.dockerenv"):
        return "container"
    if not live:
        return None
    return classify_virtualization(
        _systemd_detect_virt(which, "--container"), _systemd_detect_virt(which, "--vm")
    )


def detect_privilege(which, uid):
    if uid == 0:
        return "root"
    for tool in ("sudo", "doas"):
        if which(tool):
            return tool
    return "none"


def build_profile(root="/", env=None, which=None, uid=None):
    """Assemble the host profile. Arguments exist so tests can fake a host."""
    env = os.environ if env is None else env
    which = shutil.which if which is None else which
    uid = os.getuid() if uid is None else uid
    live = os.path.abspath(root) == "/"

    os_info = detect_os(root)
    family, support = detect_family(os_info)
    manager = PACKAGE_MANAGER.get(family)
    if not (manager and which(PACKAGE_MANAGER_BINARY[manager])):
        manager = next((name for name, binary in OTHER_MANAGERS if which(binary)), None)
    change_model = detect_change_model(root, which)
    init = detect_init(root)

    # What makes the usual commands wrong here. Nothing in it forbids a change.
    notes = []
    if family is None:
        notes.append("distribution %r is not one this skill is tested on: confirm package "
                     "and unit names on the host" % (os_info["id"] or "unknown"))
    if manager is None:
        notes.append("no known package manager was found: ask how software is installed here")
    if change_model == "image":
        notes.append("image-based system: the root is read-only and a package installed the "
                     "usual way does not persist; use the system's own tool (rpm-ostree, "
                     "bootc, transactional-update), Flatpak or a container")
    elif change_model == "declarative":
        notes.append("NixOS: system state comes from its configuration; change that and "
                     "rebuild, because edits made by hand are overwritten")
    if init == "none":
        notes.append("container with no service manager: systemctl and journalctl are absent; "
                     "start a daemon directly and stop it by its process")
    elif init != "systemd":
        notes.append("init is %s, not systemd: systemctl and journalctl are absent, use "
                     "this init's own service commands" % (init or "undetermined"))

    return {
        "schema_version": SCHEMA_VERSION,
        "os": os_info,
        "family": family,
        "support": support,
        "package_manager": manager,
        "change_model": change_model,
        "init": init,
        "mac": detect_mac(root),
        "session": detect_session(env),
        "environment": detect_environment(root, env, which, live),
        "privilege": detect_privilege(which, uid),
        "notes": notes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        default="/",
        help="inspect a filesystem tree other than the running host (default: /)",
    )
    parser.add_argument("--compact", action="store_true", help="print JSON on one line")
    args = parser.parse_args(argv)
    profile = build_profile(root=args.root)
    indent = None if args.compact else 2
    json.dump(profile, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
