#!/usr/bin/env python3
"""Journal of what an agent changed on this machine, for the linux-ops skill.

Two kinds of entry share one append-only JSONL file:

- raw events, written by the agent runtime's hook after each command or
  file edit (`hook`), so the record does not depend on the model remembering;
- changes, declared by the agent with their undo command (`record`).

Writes only inside the state directory. Never runs an undo command itself.
Runs on Python 3.6+ with the standard library only.
"""

import argparse
import fcntl
import json
import os
import re
import sys
import time

SCHEMA_VERSION = 1


def state_dir(env=None, root="/"):
    """Directory holding this machine's journal and snapshots."""
    env = os.environ if env is None else env
    if env.get("LINUX_OPS_STATE"):
        return env["LINUX_OPS_STATE"]
    base = env.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    try:
        with open(os.path.join(root, "etc/machine-id")) as handle:
            machine = handle.read().strip() or "unknown"
    except OSError:
        machine = "unknown"
    # One directory per machine, so a journal carried to another host stays apart.
    home = os.path.join(base, "linux-ops")
    target = os.path.join(home, machine)
    # A machine-id that appears or is emptied later (a fresh image, a container) must
    # not split the journal in two: "unknown" and the one real id are the same machine.
    try:
        if not os.path.isdir(target):
            others = sorted(os.listdir(home))
            if machine != "unknown" and "unknown" in others:
                os.rename(os.path.join(home, "unknown"), target)
            elif machine == "unknown" and len(others) == 1:
                target = os.path.join(home, others[0])
    except OSError:
        pass
    return target


def _path(directory):
    return os.path.join(directory, "journal.jsonl")


def read_entries(directory):
    entries = []
    try:
        with open(_path(directory), encoding="utf-8") as handle:
            for line in handle:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue  # a torn line must not hide the rest of the journal
    except OSError:
        pass
    return entries


def append(directory, entry):
    """Append one entry and return it with its id and timestamp."""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd = os.open(_path(directory), os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "rb+") as handle:
        # Agents run tool calls in parallel: without the lock two entries share an id.
        fcntl.flock(handle, fcntl.LOCK_EX)
        # The id is the line number. Counting bytes keeps the hook fast on a long journal.
        # shortcut: the journal is never rotated; add rotation if its size becomes a complaint.
        handle.seek(0)
        lines = sum(chunk.count(b"\n") for chunk in iter(lambda: handle.read(1 << 20), b""))
        entry = dict(entry, id=lines + 1, ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                     schema_version=SCHEMA_VERSION)
        handle.write((json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
    return entry


# Credential values: NAME=value and NAME: value, --name value, the password in
# a URL, and the few tools that take one in a short flag. A bare word such as
# `passwd -u paulo` is left alone, so a recorded undo command stays runnable.
# shortcut: common spellings only; widen the lists when a real leak shows one.
_NAME = r"(?:pass(?:word|wd)?|token|secret|api[_-]?key|access[_-]?key|authorization)"
_VALUE = r"(?:\"[^\"]*\"|'[^']*'|[^\s\"';|&]+)"
SECRETS = tuple(re.compile(pattern) for pattern in (
    # First: `-psecret` would otherwise read as a flag named "secret".
    r"(\b(?:sshpass|mysql|mysqldump|mariadb)\b[^|;&]*?\s-p\s?)" + _VALUE,
    r"(?i)((?<![/\w-])[\w-]*" + _NAME + r"[\w-]*[\"']?\s*[=:]\s*(?:bearer\s+)?)" + _VALUE,
    r"(?i)((?<![\w-])--?[\w-]*" + _NAME + r"[\w-]*\s+)" + _VALUE,
    r"(\b(?:curl|wget)\b[^|;&]*?\s(?:-u\s*|--user[\s=]+)[^\s:]+:)\S+",
    r"(://[^/\s:@]+:)[^@\s]+(?=@)",
    r"(://)[A-Za-z0-9_-]{20,}(?=@)",  # a token as the URL's user
    # Everyday admin tools that take the secret as a bare word.
    r"(\bnmcli\b[^|;&]*?\s(?:password|psk|[\w.-]+\.(?:psk|password))\s+)" + _VALUE,
    r"(\b(?:docker|podman)\s+login\b[^|;&]*?\s-p\s?)" + _VALUE,
    r"(\bredis-cli\b[^|;&]*?\s-a\s+)" + _VALUE,
    r"(\bhtpasswd\s+-\w*b\w*\s+\S+\s+\S+\s+)" + _VALUE,
    r"(\bsmbclient\b[^|;&]*?\s-U\s*[^\s%]+%)\S+",
    r"(\baws\s+configure\s+set\s+\S+\s+)" + _VALUE,
    r"(?i)(\blogin\s+\S+\s+password\s+)" + _VALUE,  # .netrc
    r"(\b(?:echo|printf)\s+[\"']?[^\s:\"'|]+:)[^\s\"'|]+(?=[\"']?\s*\|\s*(?:sudo\s+)?chpasswd)",
    r"(\b(?:echo|printf)\s+)" + _VALUE + r"(?=\s*\|\s*sudo\s+(?:-\S+\s+)*-\w*S)",
    r"(?s)(-----BEGIN [A-Z ]*PRIVATE KEY-----).*?-----END [A-Z ]*PRIVATE KEY-----",
))
# A call to one of this skill's own scripts and nothing else: anything that could
# chain, pipe or redirect it into a second command is logged like any other.
OWN_CALL = re.compile(r"^\s*(?:cd\s+[^\s;&|<>$`]+\s*(?:&&|;)\s*)?(?:\w+=\S+\s+)*(?:sudo\s+(?:-\S+\s+)*)?python3?\s+(?:\S*/)?"
                      r"(?:journal|state|detect_host)\.py\b[^;&|<>$`\n]*$")
# A heredoc can carry a whole file; the journal needs the command, not the payload.
MAX_COMMAND = 4000

# Tool names per runtime: Claude Code and Codex, then Antigravity.
SHELL_TOOLS = ("Bash", "run_command")
FILE_TOOLS = ("Write", "Edit", "write_to_file", "replace_file_content",
              "multi_replace_file_content")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def redact(command):
    """Mask credential values so the journal can be read and shared."""
    for pattern in SECRETS:
        command = pattern.sub(r"\1[redacted]", command)
    return command


def events_from_hook(payload):
    """Turn a PostToolUse payload from any supported runtime into journal entries."""
    call = payload.get("toolCall") or {}
    tool = payload.get("tool_name") or call.get("name")
    args = payload.get("tool_input") or call.get("args") or {}
    cwd = payload.get("cwd") or args.get("Cwd") or (payload.get("workspacePaths") or [""])[0]
    base = {"session": payload.get("session_id") or payload.get("conversationId"), "cwd": cwd}
    command = args.get("command") or args.get("CommandLine") or ""
    if tool in SHELL_TOOLS:
        if isinstance(command, list):  # some runtimes send argv instead of a line
            command = " ".join(str(part) for part in command)
        if not command or OWN_CALL.match(command):
            return []
        command = redact(command)
        if len(command) > MAX_COMMAND:
            command = command[:MAX_COMMAND] + " [... %d more characters]" % (
                len(command) - MAX_COMMAND)
        return [dict(base, kind="command", command=command)]
    if tool == "apply_patch":  # Codex sends the whole patch as the command
        paths = PATCH_FILE.findall(command)
    elif tool in FILE_TOOLS:
        paths = [args.get("file_path") or args.get("TargetFile") or ""]
    else:
        return []
    events = []
    for path in paths:
        path = os.path.abspath(os.path.join(cwd, path.strip())) if path else ""
        if path and not _in_repository(path):
            events.append(dict(base, kind="file", path=path, tool=tool))
    return events


def _in_repository(path):
    """True inside a Git work tree: those edits are the project's history, not the machine's.

    The session's directory says nothing: an agent started in ~ or / edits ~/.bashrc and /etc.
    """
    folder = os.path.dirname(path)
    while True:
        if os.path.exists(os.path.join(folder, ".git")):
            return True
        parent = os.path.dirname(folder)
        if parent == folder:
            return False
        folder = parent


def changes(entries):
    """Return declared changes, each with `undone` set from later entries."""
    undone = {entry.get("ref") for entry in entries if entry.get("kind") == "undone"}
    return [dict(entry, undone=entry["id"] in undone)
            for entry in entries if entry.get("kind") == "change"]


def unrecorded(entries):
    """Raw events logged by the hook after the last declared change or undo."""
    last = max([i for i, entry in enumerate(entries)
                if entry.get("kind") in ("change", "undone")] or [-1])
    return [entry for entry in entries[last + 1:] if entry.get("kind") in ("command", "file")]


def format_change(change):
    line = "#%d %s %s  %s" % (change["id"], change["ts"][:16].replace("T", " "),
                              "undone" if change["undone"] else "active", change["what"])
    for key in ("undo", "backup", "verify"):
        if change.get(key):
            line += "\n    %s: %s" % (key, change[key])
    return line


def context(directory, profile):
    """Text for the start of a session: the host and the latest changes."""
    os_info = profile.get("os") or {}
    mac = profile.get("mac") or {}
    lines = ["linux-ops host: %s; package manager %s; init %s; session %s; %s." % (
        os_info.get("pretty_name") or os_info.get("id") or "unknown",
        profile.get("package_manager"),
        profile.get("init"),
        (profile.get("session") or {}).get("type"),
        "%s %s" % (mac["system"], mac["state"]) if mac.get("system") else "no MAC")]
    lines.extend("Note: %s." % note for note in profile.get("notes") or [])
    # The session knows the script names from here on, so it must know where they are.
    lines.append("linux-ops scripts (journal.py, state.py, detect_host.py): %s"
                 % os.path.dirname(os.path.abspath(__file__)))
    entries = read_entries(directory)
    recorded = changes(entries)
    if recorded:
        lines.append("%d change(s) recorded on this machine by earlier sessions; latest:"
                     % len(recorded))
        lines.extend(format_change(change) for change in recorded[-5:])
    else:
        lines.append("No changes recorded on this machine yet.")
    loose = unrecorded(entries)
    if loose:
        # Without this line a change the model forgot to record would be invisible.
        lines.append("%d agent command(s) or file edit(s) were logged after the last recorded "
                     "change (most are reads). If a change seems to be missing above, "
                     "`journal.py list --unrecorded` shows them." % len(loose))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action")
    sub.required = True
    sub.add_parser("hook", help="append the tool call read from stdin (PostToolUse payload)")
    record = sub.add_parser("record", help="declare one change and how to undo it")
    record.add_argument("--what", required=True, help="the change, in one sentence")
    record.add_argument("--undo", required=True,
                        help="command that reverses it, or 'none' if irreversible")
    record.add_argument("--backup", help="path of the backup taken before the change")
    record.add_argument("--verify", help="command that proves the change is in effect")
    record.add_argument("--keep", action="store_true",
                        help="store --undo and --verify as written: they hold no secret")
    listing = sub.add_parser("list", help="print recorded changes")
    listing.add_argument("--active", action="store_true", help="leave out undone changes")
    listing.add_argument("--all", action="store_true",
                         help="print every raw entry as JSON, commands included")
    listing.add_argument("--unrecorded", action="store_true",
                         help="print what the hook logged after the last recorded change")
    show = sub.add_parser("show", help="print one change with its undo command")
    show.add_argument("id", type=int)
    undone = sub.add_parser("undone", help="mark a change as undone, after undoing it")
    undone.add_argument("id", type=int)
    sub.add_parser("where", help="print where the data is kept and how much there is")
    ctx = sub.add_parser("context", help="print the host and the latest changes")
    ctx.add_argument("--format", choices=("text", "antigravity"), default="text",
                     help="text for Claude Code and Codex hooks; antigravity for its JSON")
    args = parser.parse_args(argv)
    directory = state_dir()

    if args.action == "hook":
        # A hook must never break the user's session, whatever it is fed.
        try:
            # LINUX_OPS_NO_LOG turns the automatic log off; `record` still works.
            for entry in ([] if os.environ.get("LINUX_OPS_NO_LOG")
                          else events_from_hook(json.load(sys.stdin))):
                append(directory, entry)
        except Exception:  # noqa: BLE001
            pass
        print("{}")  # Antigravity requires a JSON answer; the others accept one
        return 0

    if args.action == "record":
        # A masked undo is a broken undo, and a later session runs it as stored.
        if not args.keep and any(text and redact(text) != text
                                 for text in (args.undo, args.verify)):
            print("not recorded: --undo or --verify contains what looks like a credential, "
                  "and masking it would break the command. Read the secret from a file or "
                  "variable instead; if there is no secret in it, repeat with --keep.",
                  file=sys.stderr)
            return 2
        entry = append(directory, {"kind": "change", "what": redact(args.what),
                                   "undo": args.undo, "backup": args.backup,
                                   "verify": args.verify})
        # The count saves the caller a `list` to see that it landed.
        print("recorded change #%d (%d active)" % (entry["id"], sum(
            not change["undone"] for change in changes(read_entries(directory)))))
        return 0

    if args.action == "context":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import detect_host
        text = context(directory, detect_host.build_profile())
        if args.format == "antigravity":
            text = json.dumps({"injectSteps": [{"systemMessage": {"systemMessage": text}}]})
        print(text)
        return 0

    entries = read_entries(directory)
    if args.action == "where":
        size = sum(os.path.getsize(os.path.join(folder, name))
                   for folder, _, names in os.walk(directory) for name in names)
        print("%s\n%d journal entries (%d logged commands or edits, %d recorded changes), "
              "%.1f MB with snapshots.\nThese scripts send nothing anywhere; what the agent "
              "reads from here goes to its model provider like any other tool output. Deleting "
              "this directory erases all of it; LINUX_OPS_NO_LOG=1 stops the automatic log."
              % (directory, len(entries), sum(e.get("kind") in ("command", "file")
                                              for e in entries),
                 len(changes(entries)), size / 1e6))
        return 0
    if args.action == "list":
        if args.all:
            for entry in entries:
                print(json.dumps(entry, sort_keys=True))
            return 0
        if args.unrecorded:
            print("\n".join("%s  %s" % (entry["ts"][:16], entry.get("command") or
                                        "edited " + entry.get("path", "?"))
                            for entry in unrecorded(entries)) or "nothing unrecorded")
            return 0
        recorded = [c for c in changes(entries) if not (args.active and c["undone"])]
        print("\n".join(format_change(c) for c in recorded) or "no changes recorded")
        return 0

    match = [c for c in changes(entries) if c["id"] == args.id]
    if not match:
        print("no change #%d in %s" % (args.id, _path(directory)), file=sys.stderr)
        return 1
    if args.action == "undone":
        append(directory, {"kind": "undone", "ref": args.id})
        print("marked change #%d as undone" % args.id)
    else:
        print(format_change(match[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
