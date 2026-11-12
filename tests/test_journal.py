"""Tests for journal.py against a temporary state directory."""

import importlib.util
import io
import json
import os
import stat

import pytest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "linux-ops", "scripts", "journal.py"
)
spec = importlib.util.spec_from_file_location("journal", SCRIPT)
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("LINUX_OPS_STATE", str(tmp_path / "state"))
    return str(tmp_path / "state")


@pytest.fixture(autouse=True)
def fake_repositories(monkeypatch):
    """The payload paths below do not exist: /home/u/p and /w stand for Git work trees."""
    monkeypatch.setattr(journal, "_in_repository",
                        lambda path: path.startswith(("/home/u/p/", "/w/")))


def hook(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return journal.main(["hook"])


def test_state_dir_is_per_machine(tmp_path):
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "machine-id").write_text("abc123\n")
    env = {"XDG_STATE_HOME": "/s"}
    assert journal.state_dir(env, str(tmp_path)) == "/s/linux-ops/abc123"
    assert journal.state_dir(env, "/nonexistent").endswith("/unknown")


def test_state_dir_survives_a_machine_id_that_appears_or_goes(tmp_path):
    (tmp_path / "etc").mkdir()
    env = {"XDG_STATE_HOME": str(tmp_path / "s")}
    home = tmp_path / "s" / "linux-ops"
    (home / "unknown").mkdir(parents=True)
    (home / "unknown" / "journal.jsonl").write_text("{}\n")
    (tmp_path / "etc" / "machine-id").write_text("abc123\n")
    # The id appeared after the journal was started: same machine, same journal.
    assert journal.state_dir(env, str(tmp_path)) == str(home / "abc123")
    assert (home / "abc123" / "journal.jsonl").exists() and not (home / "unknown").exists()
    (tmp_path / "etc" / "machine-id").write_text("")
    assert journal.state_dir(env, str(tmp_path)) == str(home / "abc123")
    # Another machine's journal, carried over, is not adopted.
    (tmp_path / "etc" / "machine-id").write_text("zzz999\n")
    assert journal.state_dir(env, str(tmp_path)) == str(home / "zzz999")


def test_hook_records_commands_and_outside_edits(state, monkeypatch):
    bash = {"tool_name": "Bash", "session_id": "s", "cwd": "/home/u/p",
            "tool_input": {"command": "sudo dnf install nginx"}}
    outside = {"tool_name": "Edit", "cwd": "/home/u/p",
               "tool_input": {"file_path": "/home/u/.config/x.conf"}}
    inside = {"tool_name": "Write", "cwd": "/home/u/p",
              "tool_input": {"file_path": "/home/u/p/a.py"}}
    own = {"tool_name": "Bash", "tool_input": {"command": "python3 journal.py list"}}
    for payload in (bash, outside, inside, own):
        assert hook(monkeypatch, json.dumps(payload)) == 0
    entries = journal.read_entries(state)
    assert [e["kind"] for e in entries] == ["command", "file"]
    assert entries[0]["command"] == "sudo dnf install nginx"
    assert entries[1]["path"] == "/home/u/.config/x.conf"


def test_hook_survives_garbage(state, monkeypatch):
    assert hook(monkeypatch, "not json") == 0
    assert hook(monkeypatch, "[]") == 0
    assert journal.read_entries(state) == []


def test_journal_file_is_private(state):
    journal.append(state, {"kind": "command", "command": "true"})
    mode = stat.S_IMODE(os.stat(os.path.join(state, "journal.jsonl")).st_mode)
    assert mode == 0o600


def test_record_show_undone_list(state, capsys):
    assert journal.main(["record", "--what", "Install nginx",
                         "--undo", "dnf remove nginx"]) == 0
    assert journal.main(["record", "--what", "Open port 8080", "--undo", "none",
                         "--backup", "/etc/nginx/nginx.conf.bak"]) == 0
    assert journal.main(["show", "1"]) == 0
    assert "undo: dnf remove nginx" in capsys.readouterr().out
    assert journal.main(["undone", "1"]) == 0
    assert journal.main(["show", "9"]) == 1
    capsys.readouterr()
    journal.main(["list"])
    listed = capsys.readouterr().out
    assert "#1" in listed and "undone  Install nginx" in listed
    assert "backup: /etc/nginx/nginx.conf.bak" in listed
    journal.main(["list", "--active"])
    active = capsys.readouterr().out
    assert "Install nginx" not in active and "Open port 8080" in active


def test_torn_line_does_not_hide_entries(state):
    journal.append(state, {"kind": "change", "what": "a", "undo": "b"})
    with open(os.path.join(state, "journal.jsonl"), "a") as handle:
        handle.write('{"kind": "chan\n')
    journal.append(state, {"kind": "change", "what": "c", "undo": "d"})
    assert [c["what"] for c in journal.changes(journal.read_entries(state))] == ["a", "c"]


def test_context_names_host_and_latest_changes(state):
    profile = {"os": {"pretty_name": "Fedora Linux 44"}, "package_manager": "dnf",
               "session": {"type": "wayland"}, "init": "systemd", "notes": ["image-based"],
               "mac": {"system": "selinux", "state": "enforcing"}}
    assert "No changes recorded" in journal.context(state, profile)
    journal.append(state, {"kind": "change", "what": "Install nginx", "undo": "x"})
    text = journal.context(state, profile)
    assert "Fedora Linux 44" in text and "selinux enforcing" in text
    assert "Note: image-based." in text and "logged after" not in text
    assert "1 change(s)" in text and "Install nginx" in text


def test_commands_nobody_recorded_are_surfaced(state, capsys):
    journal.append(state, {"kind": "command", "command": "dnf install old"})
    journal.append(state, {"kind": "change", "what": "x", "undo": "y"})
    journal.append(state, {"kind": "command", "command": "dnf remove firewalld"})
    assert "1 agent command(s)" in journal.context(state, {})
    journal.main(["list", "--unrecorded"])
    out = capsys.readouterr().out
    assert "dnf remove firewalld" in out and "dnf install old" not in out


def test_no_log_switch_and_where(state, monkeypatch, capsys):
    monkeypatch.setenv("LINUX_OPS_NO_LOG", "1")
    hook(monkeypatch, json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
    assert journal.read_entries(state) == []
    journal.main(["where"])
    assert state in capsys.readouterr().out


def test_only_a_pure_call_to_our_scripts_is_skipped():
    def events(command):
        return journal.events_from_hook({"tool_name": "Bash", "tool_input": {"command": command}})
    assert events("LINUX_OPS_STATE=/s python3 /p/state.py diff 20261101T101010.json") == []
    assert events(["python3", "journal.py", "list"]) == []  # argv instead of a line
    assert events("cd /p/scripts && python3 journal.py record --what a --undo b") == []
    assert len(events("cd /etc && rm -rf x; python3 journal.py list")) == 1
    for logged in ("dnf remove x && python3 journal.py record --what a --undo b",
                   "cat /etc/shadow # state.py",
                   "python3 /p/state.py snapshot\nsudo dnf remove firewalld",
                   "python3 journal.py list | sh",
                   "python3 state.py list > /etc/fstab",
                   "python3 state.py list $(rm -rf /x)",
                   "sudo python3 manage_state.py --apply"):
        assert len(events(logged)) == 1, logged


def test_edits_are_logged_unless_inside_a_git_work_tree(tmp_path, monkeypatch):
    monkeypatch.undo()  # the real check, on real folders
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "src").mkdir()

    def paths(target, cwd):
        return [e["path"] for e in journal.events_from_hook(
            {"tool_name": "Edit", "cwd": cwd, "tool_input": {"file_path": target}})]
    assert paths(str(tmp_path / "repo" / "src" / "a.py"), str(tmp_path)) == []
    # An agent started in ~ or / edits the machine, not a project.
    dotfile = str(tmp_path / ".bashrc")
    assert paths(dotfile, str(tmp_path)) == [dotfile]
    assert paths("/etc/hosts", "/") == ["/etc/hosts"]
    # Dotfiles kept in a repository at ~ are still the machine; a project inside ~ is not.
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    (home / "project" / ".git").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    assert paths(str(home / ".bashrc"), str(home)) == [str(home / ".bashrc")]
    assert paths(str(home / "project" / "a.py"), str(home)) == []


def test_parallel_appends_get_distinct_ids(state):
    import threading
    threads = [threading.Thread(target=journal.append,
                                args=(state, {"kind": "command", "command": "true"}))
               for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(e["id"] for e in journal.read_entries(state)) == list(range(1, 21))


def test_long_commands_are_cut():
    event = journal.events_from_hook(
        {"tool_name": "Bash", "tool_input": {"command": "cat > f <<EOF\n" + "x" * 9000}})[0]
    assert len(event["command"]) < 4100 and "more characters" in event["command"]


def test_record_refuses_an_undo_that_masking_would_break(state, capsys):
    broken = "sed -i 's/^PasswordAuthentication=no//' /etc/ssh/sshd_config"
    assert journal.main(["record", "--what", "x", "--undo", broken]) == 2
    assert "--keep" in capsys.readouterr().err and journal.read_entries(state) == []
    assert journal.main(["record", "--what", "set password=hunter2", "--undo", broken,
                         "--keep"]) == 0
    entry = journal.read_entries(state)[0]
    assert entry["undo"] == broken and "hunter2" not in entry["what"]


def test_redact_everyday_admin_tools():
    for command, secret in (
            ("nmcli device wifi connect Home password hunter2", "hunter2"),
            ("nmcli con modify Home wifi-sec.psk hunter2", "hunter2"),
            ("echo 'ana:hunter2' | sudo chpasswd", "hunter2"),
            ("echo hunter2 | sudo -S dnf install x", "hunter2"),
            ("curl -uadmin:hunter2 https://x", "hunter2"),
            ("docker login -u me -p hunter2 ghcr.io", "hunter2"),
            ("htpasswd -b /etc/nginx/.htpasswd ana hunter2", "hunter2"),
            ("smbclient //h/s -U ana%hunter2", "hunter2"),
            ("redis-cli -a hunter2 ping", "hunter2"),
            ("aws configure set aws_secret_access_key hunter2", "hunter2"),
            ("git clone https://ghp_abcdefghijklmnopqrstuvwx@github.com/a/b", "ghp_abc"),
            ("echo 'machine h login me password hunter2' >> ~/.netrc", "hunter2"),
            ("cat > k <<E\n-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAhunter2\n"
             "-----END OPENSSH PRIVATE KEY-----\nE", "hunter2")):
        assert secret not in journal.redact(command), command
    for kept in ("docker run -p 8080:80 img", "nmcli con show Home",
                 "echo ok | sudo tee /etc/x", "git clone https://github.com/a/b"):
        assert journal.redact(kept) == kept


def test_redact_quoted_and_short_flag_values_and_spares_plain_words():
    assert journal.redact('export TOKEN="my secret"') == "export TOKEN=[redacted]"
    assert journal.redact("curl -u me:pw https://x") == "curl -u me:[redacted] https://x"
    assert journal.redact("mysql -psecret db") == "mysql -p[redacted] db"
    assert journal.redact("sshpass -p hunter2 ssh h") == "sshpass -p [redacted] ssh h"
    for kept in ("passwd -u paulo", 'git commit -m "fix password reset"',
                 "podman run -v /etc/passwd:/etc/passwd:ro img", "podman run -u 1000:1000 img"):
        assert journal.redact(kept) == kept


def test_redact_masks_credentials_and_keeps_the_rest():
    assert journal.redact("curl -H 'Authorization: Bearer abc.def' https://x") == \
        "curl -H 'Authorization: Bearer [redacted]' https://x"
    assert journal.redact("mysql --password=hunter2 -u root") == \
        "mysql --password=[redacted] -u root"
    assert journal.redact("export API_KEY=sk-123; run") == "export API_KEY=[redacted]; run"
    assert journal.redact("git clone https://me:s3cret@host/r.git") == \
        "git clone https://me:[redacted]@host/r.git"
    assert journal.redact("dnf -y install nginx") == "dnf -y install nginx"


def test_hook_redacts_before_writing(state, monkeypatch):
    hook(monkeypatch, json.dumps({"tool_name": "Bash", "cwd": "/r",
                                  "tool_input": {"command": "login --token abc123"}}))
    assert journal.read_entries(state)[0]["command"] == "login --token [redacted]"


def test_codex_apply_patch_records_files_outside_the_project():
    patch = "*** Begin Patch\n*** Update File: src/a.py\n@@\n*** Add File: /etc/x.conf\n"
    events = journal.events_from_hook({"tool_name": "apply_patch", "cwd": "/home/u/p",
                                       "session_id": "s", "tool_input": {"command": patch}})
    assert [e["path"] for e in events] == ["/etc/x.conf"]


def test_antigravity_payloads():
    shell = {"toolCall": {"name": "run_command",
                          "args": {"CommandLine": "sudo apt install nginx", "Cwd": "/w"}},
             "conversationId": "c1", "workspacePaths": ["/w"]}
    edit = {"toolCall": {"name": "replace_file_content",
                         "args": {"TargetFile": "/etc/hosts"}},
            "conversationId": "c1", "workspacePaths": ["/w"]}
    inside = {"toolCall": {"name": "write_to_file", "args": {"TargetFile": "/w/a.txt"}},
              "workspacePaths": ["/w"]}
    first = journal.events_from_hook(shell)[0]
    assert (first["command"], first["session"], first["cwd"]) == \
        ("sudo apt install nginx", "c1", "/w")
    assert journal.events_from_hook(edit)[0]["path"] == "/etc/hosts"
    assert journal.events_from_hook(inside) == []
    assert journal.events_from_hook({"toolCall": {"name": "view_file", "args": {}}}) == []


def test_hook_always_answers_json(state, monkeypatch, capsys):
    hook(monkeypatch, "garbage")
    assert capsys.readouterr().out.strip() == "{}"


def test_context_antigravity_format(state, capsys):
    assert journal.main(["context", "--format", "antigravity"]) == 0
    step = json.loads(capsys.readouterr().out)["injectSteps"][0]
    assert "linux-ops host:" in step["systemMessage"]["systemMessage"]
