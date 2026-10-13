"""Tests for detect_host.py against fake host trees."""

import importlib.util
import json
import os
import subprocess
import sys

import pytest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "linux-ops", "scripts", "detect_host.py"
)
spec = importlib.util.spec_from_file_location("detect_host", SCRIPT)
detect_host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detect_host)

OS_RELEASE = {
    "fedora": 'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=44\nVARIANT_ID=kde\n'
    'PRETTY_NAME="Fedora Linux 44 (KDE Plasma Desktop Edition)"\n',
    "silverblue": 'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=44\nVARIANT_ID=silverblue\n',
    "debian": 'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\nVERSION_ID="13"\n',
    "ubuntu": 'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_ID="24.04"\n',
    "arch": 'NAME="Arch Linux"\nID=arch\nBUILD_ID=rolling\n',
    "tumbleweed": 'NAME="openSUSE Tumbleweed"\nID="opensuse-tumbleweed"\n'
    'ID_LIKE="opensuse suse"\nVERSION_ID="20261001"\n',
    "leap": 'NAME="openSUSE Leap"\nID="opensuse-leap"\nID_LIKE="suse opensuse"\n'
    'VERSION_ID="15.6"\n',
    "microos": 'NAME="openSUSE MicroOS"\nID="opensuse-microos"\n'
    'ID_LIKE="suse opensuse opensuse-tumbleweed"\n',
    "rocky": 'NAME="Rocky Linux"\nID="rocky"\nID_LIKE="rhel centos fedora"\nVERSION_ID="9.4"\n',
    "mint": 'NAME="Linux Mint"\nID=linuxmint\nID_LIKE="ubuntu debian"\nVERSION_ID="22"\n',
    "manjaro": 'NAME="Manjaro Linux"\nID=manjaro\nID_LIKE=arch\n',
    "alpine": 'NAME="Alpine Linux"\nID=alpine\nVERSION_ID=3.20.0\n',
    "nixos": 'NAME=NixOS\nID=nixos\nVERSION_ID="24.05"\n',
}


def make_host(tmp_path, release, systemd=True, files=None):
    """Build a fake root tree and return its path."""
    files = dict(files or {})
    files["etc/os-release"] = OS_RELEASE[release]
    if systemd:
        files["run/systemd/system/.keep"] = ""
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return str(tmp_path)


def profile(root, binaries=(), env=None, uid=1000):
    present = set(binaries)
    return detect_host.build_profile(
        root=root,
        env=env or {},
        which=lambda name: "/usr/bin/" + name if name in present else None,
        uid=uid,
    )


@pytest.mark.parametrize(
    "release,binary,family,manager",
    [
        ("fedora", "dnf", "fedora", "dnf"),
        ("debian", "apt-get", "debian", "apt"),
        ("ubuntu", "apt-get", "debian", "apt"),
        ("arch", "pacman", "arch", "pacman"),
        ("tumbleweed", "zypper", "suse", "zypper"),
        ("leap", "zypper", "suse", "zypper"),
    ],
)
def test_tier1_hosts_are_read_write(tmp_path, release, binary, family, manager):
    result = profile(make_host(tmp_path, release), binaries=[binary, "sudo"])
    assert result["family"] == family
    assert result["support"] == "tier1"
    assert result["package_manager"] == manager
    assert result["change_model"] == "imperative"
    assert result["mode"] == "read-write"
    assert result["read_only_reasons"] == []


@pytest.mark.parametrize(
    "release,binary,family",
    [
        ("rocky", "dnf", "fedora"),
        ("mint", "apt-get", "debian"),
        ("manjaro", "pacman", "arch"),
    ],
)
def test_derivatives_resolve_through_id_like(tmp_path, release, binary, family):
    result = profile(make_host(tmp_path, release), binaries=[binary])
    assert result["family"] == family
    assert result["support"] == "derivative"
    assert result["mode"] == "read-write"


@pytest.mark.parametrize("release", ["alpine", "nixos"])
def test_unknown_family_is_read_only(tmp_path, release):
    files = {"etc/NIXOS": ""} if release == "nixos" else {}
    result = profile(make_host(tmp_path, release, files=files), binaries=["apk"])
    assert result["family"] is None
    assert result["support"] == "unsupported"
    assert result["package_manager"] is None
    assert result["mode"] == "read-only"
    assert any("outside the supported families" in r for r in result["read_only_reasons"])


def test_ostree_host_is_image_based_and_read_only(tmp_path):
    root = make_host(tmp_path, "silverblue", files={"run/ostree-booted": ""})
    result = profile(root, binaries=["dnf", "rpm-ostree"])
    assert result["family"] == "fedora"
    assert result["change_model"] == "image"
    assert result["mode"] == "read-only"


def test_transactional_host_is_image_based(tmp_path):
    mounts = "/dev/sda2 / btrfs ro,relatime 0 0\n/dev/sda2 /var btrfs rw 0 0\n"
    root = make_host(tmp_path, "microos", files={"proc/mounts": mounts})
    result = profile(root, binaries=["zypper", "transactional-update"])
    assert result["family"] == "suse"
    assert result["support"] == "derivative"
    assert result["change_model"] == "image"
    assert result["mode"] == "read-only"


def test_transactional_update_on_writable_root_stays_imperative(tmp_path):
    mounts = "/dev/sda2 / btrfs rw,relatime 0 0\n"
    root = make_host(tmp_path, "tumbleweed", files={"proc/mounts": mounts})
    result = profile(root, binaries=["zypper", "transactional-update"])
    assert result["change_model"] == "imperative"
    assert result["mode"] == "read-write"


def test_missing_systemd_is_read_only(tmp_path):
    root = make_host(tmp_path, "debian", systemd=False, files={"proc/1/comm": "bash\n"})
    result = profile(root, binaries=["apt-get"])
    assert result["init"] == "bash"
    assert result["mode"] == "read-only"
    assert result["read_only_reasons"] == ["init is bash, not systemd"]


def test_missing_package_manager_is_read_only(tmp_path):
    result = profile(make_host(tmp_path, "fedora"))
    assert result["package_manager"] is None
    assert result["read_only_reasons"] == ["package manager dnf is not installed"]


def test_missing_os_release_is_read_only(tmp_path):
    (tmp_path / "run/systemd/system").mkdir(parents=True)
    result = profile(str(tmp_path))
    assert result["os"]["id"] is None
    assert result["mode"] == "read-only"


def test_mac_detection(tmp_path):
    root = make_host(tmp_path, "fedora", files={"sys/fs/selinux/enforce": "1"})
    assert profile(root)["mac"] == {"system": "selinux", "state": "enforcing"}


def test_mac_permissive_and_apparmor(tmp_path):
    selinux = make_host(tmp_path / "a", "fedora", files={"sys/fs/selinux/enforce": "0"})
    assert profile(selinux)["mac"]["state"] == "permissive"
    apparmor = make_host(
        tmp_path / "b", "ubuntu", files={"sys/module/apparmor/parameters/enabled": "Y"}
    )
    assert profile(apparmor)["mac"] == {"system": "apparmor", "state": "enabled"}
    assert profile(make_host(tmp_path / "c", "arch"))["mac"]["system"] is None


def test_session_detection(tmp_path):
    root = make_host(tmp_path, "fedora")
    wayland = profile(root, env={"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"})
    assert wayland["session"] == {"type": "wayland", "desktop": "KDE"}
    assert profile(root, env={"XDG_SESSION_TYPE": "tty", "DISPLAY": ":0"})["session"]["type"] == "x11"
    assert profile(root)["session"]["type"] == "none"


def test_environment_detection(tmp_path):
    container = make_host(tmp_path / "a", "debian", files={"run/.containerenv": ""})
    assert profile(container)["environment"] == "container"
    wsl = make_host(
        tmp_path / "b",
        "ubuntu",
        files={"proc/sys/kernel/osrelease": "5.15.153.1-microsoft-standard-WSL2\n"},
    )
    assert profile(wsl)["environment"] == "wsl"
    # A tree that is not the running host gives no evidence either way.
    assert profile(make_host(tmp_path / "c", "arch"))["environment"] is None


@pytest.mark.parametrize(
    "container,vm,expected",
    [
        ("none", "none", "physical"),
        ("none", "kvm", "vm"),
        ("podman", "kvm", "container"),
        ("container-other", "none", "sandbox"),
        ("wsl", "none", "wsl"),
        (None, None, None),
        ("none", None, None),
    ],
)
def test_virtualization_classification(container, vm, expected):
    assert detect_host.classify_virtualization(container, vm) == expected


def test_privilege_detection(tmp_path):
    root = make_host(tmp_path, "fedora")
    assert profile(root, uid=0)["privilege"] == "root"
    assert profile(root, binaries=["sudo", "doas"])["privilege"] == "sudo"
    assert profile(root, binaries=["doas"])["privilege"] == "doas"
    assert profile(root)["privilege"] == "none"


def test_os_release_parsing_handles_quotes_and_comments():
    fields = detect_host.parse_os_release(
        "# comment\nNAME='Some Linux'\nID=\"some\"\nEMPTY=\nBROKEN=\"unterminated\n\nnoequals\n"
    )
    assert fields == {"NAME": "Some Linux", "ID": "some", "EMPTY": "", "BROKEN": "unterminated"}


def test_cli_prints_valid_json(tmp_path):
    root = make_host(tmp_path, "arch")
    output = subprocess.check_output([sys.executable, SCRIPT, "--root", root, "--compact"])
    result = json.loads(output.decode())
    assert result["schema_version"] == detect_host.SCHEMA_VERSION
    assert result["family"] == "arch"
    assert output.count(b"\n") == 1
