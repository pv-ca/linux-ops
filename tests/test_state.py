"""Tests for state.py against fake host trees."""

import importlib.util
import json
import os

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "linux-ops", "scripts", "state.py"
)
spec = importlib.util.spec_from_file_location("state", SCRIPT)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)

OUTPUTS = {
    "uname": "7.2.15-200.fc44.x86_64\n",
    "systemctl": "sshd.service enabled enabled\n",
    "systemctl --user": "syncthing.service enabled enabled\n",
    "flatpak": "org.mozilla.firefox 131.0\n",
    "snap": "Name Version Rev\ncore22 20240904 1612\n",
    "mokutil": "SecureBoot enabled\n",
    "dconf": "[org/gnome/desktop/interface]\ncolor-scheme='prefer-dark'\n",
}


def fake_run(packages, **override):
    outputs = dict(OUTPUTS, **override)

    def run(command):
        key = " ".join(command[:2]) if command[:2] == ["systemctl", "--user"] else command[0]
        return outputs.get(key, packages)
    return run


def only(*tools):
    return lambda tool: "/usr/bin/" + tool if tool in tools else None


def make_tree(tmp_path, files):
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return str(tmp_path)


def snap(tmp_path, packages="bash 5.3-1\n", which=only("rpm"), **override):
    return state.take_snapshot(str(tmp_path), fake_run(packages, **override), which,
                               home=str(tmp_path / "home"))


def test_snapshot_reads_every_section(tmp_path):
    root = make_tree(tmp_path, {
        "etc/hosts": "127.0.0.1 localhost\n", "etc/nginx/nginx.conf": "a\n",
        "proc/cmdline": "root=UUID=1 quiet\n", "proc/modules": "nvidia 1 0 - Live\nxfs 2 1\n",
        "home/.config/kwinrc": "x\n", "home/.config/a/b/c/too-deep": "x\n",
        "home/.local/share/flatpak/overrides/org.app": "[Context]\n"})
    os.symlink("/nowhere", os.path.join(root, "etc", "link"))
    result = snap(tmp_path, "bash 5.3-1\nnginx 1.28-2\n")
    assert result["packages"] == {"bash": "5.3-1", "nginx": "1.28-2"}
    assert result["flatpak"] == {"org.mozilla.firefox": "131.0"}
    assert result["snap"] == {"core22": "20240904"}
    assert result["units"] == {"sshd.service": "enabled"}
    assert result["user_units"] == {"syncthing.service": "enabled"}
    assert result["modules"] == {"nvidia": "loaded", "xfs": "loaded"}
    assert sorted(result["etc"]) == ["hosts", "nginx/nginx.conf"]
    assert sorted(result["home"]) == ["flatpak-overrides/org.app", "kwinrc"]
    assert result["dconf"] == {"/org/gnome/desktop/interface/color-scheme": "'prefer-dark'"}
    assert result["cmdline"] == "root=UUID=1 quiet"
    assert result["secure_boot"] == "SecureBoot enabled"


def test_snapshot_on_a_system_with_nothing_known(tmp_path):
    result = state.take_snapshot(str(tmp_path), lambda command: "", only(),
                                 home=str(tmp_path / "home"))
    assert result["packages"] == {} and result["etc"] == {} and result["secure_boot"] is None
    assert state.diff(result, result)["identical"] is True


def test_a_manager_that_lists_nothing_is_skipped(tmp_path):
    def run(command):
        return "" if command[0] == "rpm" else "bash 5.2\n" if command[0] == "dpkg-query" else ""
    result = state.take_snapshot(str(tmp_path), run, only("rpm", "dpkg-query"),
                                 home=str(tmp_path / "home"))
    assert result["packages"] == {"bash": "5.2"}
    make_tree(tmp_path, {"var/log/dpkg.log": "2026-11-10 12:00:01 install tree:amd64 <none> 2.1\n"})
    assert len(state.package_history(str(tmp_path), run, only("rpm", "dpkg-query"))) == 1


def test_pairs_keep_versionless_and_two_architectures():
    assert state._pairs("org.a.App\t1.0\norg.b.NoVersion\n") == \
        {"org.a.App": "1.0", "org.b.NoVersion": ""}
    assert state._pairs("glibc 2.40\nglibc 2.40\n") == {"glibc": "2.40, 2.40"}


def test_services_without_systemd(tmp_path):
    make_tree(tmp_path, {"var/service/sshd/run": "x"})
    def run(command):
        return "  crond | default\n" if command[0] == "rc-update" else ""
    assert state.enabled_services(str(tmp_path), run) == {"crond": "default", "sshd": "enabled"}


def test_package_formats():
    assert state.parse_packages("apk", "busybox-1.37.0-r12 x86_64 {busybox} (GPL) [installed]\n"
                                ) == {"busybox": "1.37.0-r12"}
    assert state.parse_packages("xbps-query", "ii bash-5.2.037_1   The GNU shell\n"
                                ) == {"bash": "5.2.037_1"}
    assert state.parse_packages("pacman", "bash 5.3.0-1\n") == {"bash": "5.3.0-1"}


def test_diff_reports_each_kind_of_change(tmp_path):
    root = make_tree(tmp_path, {"etc/hosts": "a\n", "etc/old.conf": "x\n",
                                "proc/modules": "nvidia 1 0\n", "proc/cmdline": "quiet\n",
                                "home/.config/kwinrc": "x\n"})
    before = snap(tmp_path, "bash 5.3-1\nvim 9.1\n")
    make_tree(tmp_path, {"etc/hosts": "b\n", "etc/nginx/nginx.conf": "listen 8080;\n",
                         "proc/modules": "nouveau 1 0\n", "home/.config/kwinrc": "y\n"})
    os.remove(os.path.join(root, "etc", "old.conf"))
    after = snap(tmp_path, "bash 5.3-2\nnginx 1.28-2\n", uname="7.3.1\n",
                 mokutil="SecureBoot disabled\n",
                 systemctl="sshd.service enabled enabled\nnginx.service enabled disabled\n")
    result = state.diff(before, after)
    assert result["packages"] == {"added": ["nginx"], "removed": ["vim"], "changed": ["bash"]}
    assert result["units"]["added"] == ["nginx.service"]
    assert result["etc"] == {"added": ["nginx/nginx.conf"], "removed": ["old.conf"],
                             "changed": ["hosts"]}
    assert result["modules"] == {"added": ["nouveau"], "removed": ["nvidia"], "changed": []}
    assert result["home"]["changed"] == ["kwinrc"]
    assert result["kernel"] == {"from": "7.2.15-200.fc44.x86_64", "to": "7.3.1"}
    assert result["secure_boot"]["to"] == "SecureBoot disabled"
    assert result["cmdline"] is None and result["identical"] is False


def test_diff_accepts_snapshots_from_schema_1():
    old = {"ts": "t", "kernel": "k", "packages": {"a": "1"}, "units": {}, "etc": {}}
    assert state.diff(old, old)["identical"] is True
    # A section the old snapshot never had is not reported as all new.
    new = dict(old, accounts={"user:root": "present"})
    assert state.diff(old, new)["identical"] is True


def test_accounts_and_text_diff(tmp_path):
    root = make_tree(tmp_path, {"etc/passwd": "root:x:0:0::/root:/bin/sh\n",
                                "etc/group": "root:x:0:\n"})
    old = snap(tmp_path, "bash 5.2-1\n")
    assert old["accounts"] == {"user:root": "present", "group:root": "present"}
    with open(os.path.join(root, "etc", "passwd"), "a") as handle:
        handle.write("nginx:x:990:990::/var/lib/nginx:/sbin/nologin\n")
    new = snap(tmp_path, "bash 5.3-1\n" + "".join("p%02d 1\n" % n for n in range(25)))
    text = state.format_diff(old, new)
    assert "accounts added (1): user:nginx" in text
    assert "packages changed (1): bash 5.2-1 -> 5.3-1" in text
    assert "packages added (25): p00, " in text and "+5 more" in text
    assert "matches that snapshot" in state.format_diff(old, old)


def test_snapshot_names_are_forgiving():
    names = ["20261110T090000.json", "20261111T160258.json", "20261111T160357.json"]
    entries = [{"id": 3, "ts": "2026-11-11T16:03:19+0000"}]
    assert state.resolve(names, "20261110T090000") == "20261110T090000.json"
    assert state.resolve(names, "latest") == names[-1]
    assert state.resolve(names, "before:3", entries) == "20261111T160258.json"
    assert state.before(names, ["2026-11-01T00:00:00+0000"]) is None


def test_plan_gives_the_undo_in_one_answer(tmp_path, monkeypatch):
    directory = str(tmp_path / "state")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(state.time, "strftime", lambda *_: "20200101T000000")
    state.save(directory, state.take_snapshot(str(tmp_path), lambda command: "", only(),
                                              home=str(tmp_path)))
    monkeypatch.undo()
    state.journal.append(directory, {"kind": "change", "what": "Install nginx",
                                     "undo": "dnf remove nginx"})
    state.journal.append(directory, {"kind": "change", "what": "Open port", "undo": "x"})
    state.journal.append(directory, {"kind": "undone", "ref": 2})
    monkeypatch.setattr(state, "take_snapshot", lambda: dict(
        state.load(directory, "20200101T000000.json"), packages={"nginx": "1.30"}))
    text = state.plan(directory, state.saved(directory))
    assert "1 active change(s)" in text and "undo: dnf remove nginx" in text
    assert "Open port" not in text and "packages added (1): nginx" in text
    assert "no active changes" in state.plan(directory, state.saved(directory), "2999-01-01")
    shown = state.status(directory, state.saved(directory))
    assert [change["id"] for change in shown["active"]] == [1] and shown["active"][0]["can_undo"]
    assert shown["latest_snapshot"] == "20200101T000000" and shown["logging"] is True


def test_history_parsers():
    dpkg = ("2026-11-10 12:00:01 upgrade bash:amd64 5.2 5.3\n"
            "2026-11-10 12:00:02 status installed bash:amd64 5.3\n"
            "2026-11-10 12:00:03 remove vim:amd64 9.1 <none>\n")
    assert state.parse_dpkg_log(dpkg) == [
        {"when": "2026-11-10T12:00:01", "action": "upgrade", "package": "bash", "version": "5.3"},
        {"when": "2026-11-10T12:00:03", "action": "remove", "package": "vim", "version": "9.1"}]
    pacman = ("[2026-11-10T12:00:00-0300] [ALPM] upgraded linux (6.11 -> 6.12)\n"
              "[2026-11-10T12:00:00-0300] [PACMAN] Running 'pacman -Syu'\n")
    assert state.parse_pacman_log(pacman) == [
        {"when": "2026-11-10T12:00:00", "action": "upgraded", "package": "linux",
         "version": "6.12"}]
    rpm = state.parse_rpm_times("1794322800 bash 5.3-1\nnot a line\n")
    assert rpm[0]["package"] == "bash" and rpm[0]["action"] == "installed-or-updated"


def test_history_reads_rotated_dpkg_logs(tmp_path):
    import gzip
    make_tree(tmp_path, {"var/log/dpkg.log": "2026-11-10 12:00:01 install b:amd64 <none> 2\n"})
    with gzip.open(str(tmp_path / "var/log/dpkg.log.2.gz"), "wt") as handle:
        handle.write("2026-10-01 08:00:00 install a:amd64 <none> 1\n")
    events = state.package_history(str(tmp_path), which=only("dpkg-query"))
    assert [event["package"] for event in events] == ["a", "b"]


def test_cli_snapshot_list_diff_history(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LINUX_OPS_STATE", str(tmp_path / "state"))
    # The real ~/.config changes while the test runs; an empty home does not.
    monkeypatch.setenv("HOME", str(tmp_path))
    assert state.main(["diff"]) == 1
    assert state.main(["snapshot"]) == 0
    assert state.main(["snapshot", "--if-older", "24"]) == 0
    capsys.readouterr()
    assert state.main(["list"]) == 0
    assert len(capsys.readouterr().out.split()) == 1
    assert state.main(["diff", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["identical"] is True
    assert state.main(["diff", "latest"]) == 0
    assert "matches that snapshot" in capsys.readouterr().out
    assert state.main(["diff", "missing"]) == 1
    assert state.main(["history", "--days", "1"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), list)


def test_save_is_private_whole_and_pruned(tmp_path, monkeypatch):
    directory = str(tmp_path / "state")
    monkeypatch.setattr(state, "KEEP", 2)
    stamps = iter(["20261101T000001", "20261102T000001", "20261103T000001"])
    monkeypatch.setattr(state.time, "strftime", lambda *_: next(stamps))
    for _ in range(3):
        state.save(directory, {"schema_version": 2})
    # No half-written file left behind, the oldest dropped.
    assert state.saved(directory) == ["20261102T000001.json", "20261103T000001.json"]
    assert os.listdir(state.snapshot_dir(directory)) == state.saved(directory) or \
        sorted(os.listdir(state.snapshot_dir(directory))) == state.saved(directory)
    for folder in (directory, state.snapshot_dir(directory)):
        assert os.stat(folder).st_mode & 0o077 == 0
