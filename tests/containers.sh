#!/usr/bin/env bash
# Run the scripts inside each tier 1 distribution's container image: a snapshot,
# the journal hook and a record, and the family and package manager detect_host.py reports.
#
# Usage: tests/containers.sh [image-substring]
# ENGINE selects the container engine (default: docker, else podman).
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
engine="${ENGINE:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
filter="${1:-}"

# image | family | package manager | command that installs python3
cases=(
  "registry.fedoraproject.org/fedora:latest|fedora|dnf|dnf -y -q install python3"
  "docker.io/library/debian:stable|debian|apt|apt-get -qq update && apt-get -qq -y install python3"
  "docker.io/library/ubuntu:latest|debian|apt|apt-get -qq update && apt-get -qq -y install python3"
  "docker.io/library/archlinux:latest|arch|pacman|pacman -Syu --noconfirm --quiet python"
  # Docker Hub mirror of the official openSUSE images: registry.opensuse.org went down during CI once.
  "docker.io/opensuse/tumbleweed:latest|suse|zypper|zypper -q -n install python3"
  "docker.io/opensuse/leap:15.6|suse|zypper|zypper -q -n install python3"
  # No family: the scripts must still profile and snapshot it.
  "docker.io/library/alpine:latest||apk|apk add -q python3"
)

failed=0
for entry in "${cases[@]}"; do
  IFS='|' read -r image family manager install <<<"$entry"
  if [[ -n "$filter" && "$image" != *"$filter"* ]]; then
    continue
  fi
  echo "== $image"
  if ! profile="$("$engine" run --rm -v "$repo:/src:ro,z" "$image" sh -c \
    "command -v python3 >/dev/null 2>&1 || { $install; } >/dev/null 2>&1
     cd /src/skills/linux-ops/scripts
     # A snapshot with no packages or no /etc means the package query is wrong here.
     LINUX_OPS_STATE=/tmp/s python3 state.py snapshot >/dev/null &&
     python3 -c 'import glob, json, sys
s = json.load(open(glob.glob(\"/tmp/s/snapshots/*.json\")[0]))
sys.exit(0 if len(s[\"packages\"]) > 20 and s[\"etc\"] else \"FAIL: empty snapshot\")' &&
     # The hook and record must work on this distribution's Python, the oldest included.
     echo '{\"tool_name\": \"Bash\", \"cwd\": \"/\", \"tool_input\": {\"command\": \"touch /etc/lo-test\"}}' |
       LINUX_OPS_STATE=/tmp/s python3 journal.py hook >/dev/null &&
     grep -q 'touch /etc/lo-test' /tmp/s/journal.jsonl &&
     LINUX_OPS_STATE=/tmp/s python3 journal.py record --what 'created /etc/lo-test' \
       --undo 'rm /etc/lo-test' >/dev/null &&
     LINUX_OPS_STATE=/tmp/s python3 journal.py list | grep -q 'created /etc/lo-test' &&
     python3 detect_host.py --compact")"; then
    echo "FAIL: could not run the scripts"
    failed=1
    continue
  fi
  echo "$profile"
  if ! EXPECT_FAMILY="$family" EXPECT_MANAGER="$manager" python3 -c '
import json, os, sys
profile = json.loads(sys.stdin.read())
family = os.environ["EXPECT_FAMILY"] or None
expected = {
    "family": family,
    "package_manager": os.environ["EXPECT_MANAGER"],
    "support": "tier1" if family else "untested",
    "change_model": "imperative",
    "environment": "container",
}
wrong = {k: (profile.get(k), v) for k, v in expected.items() if profile.get(k) != v}
if wrong:
    sys.exit("FAIL (got, expected): %r" % wrong)
print("ok")
' <<<"$profile"; then
    failed=1
  fi
done
exit "$failed"
