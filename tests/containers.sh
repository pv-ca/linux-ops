#!/usr/bin/env bash
# Run detect_host.py inside each tier 1 distribution's container image and
# check the family and package manager it reports.
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
  "docker.io/library/archlinux:latest|arch|pacman|pacman -Sy --noconfirm --quiet python"
  "registry.opensuse.org/opensuse/tumbleweed:latest|suse|zypper|zypper -q -n install python3"
  "registry.opensuse.org/opensuse/leap:15.6|suse|zypper|zypper -q -n install python3"
)

failed=0
for entry in "${cases[@]}"; do
  IFS='|' read -r image family manager install <<<"$entry"
  if [[ -n "$filter" && "$image" != *"$filter"* ]]; then
    continue
  fi
  echo "== $image"
  if ! profile="$("$engine" run --rm -v "$repo:/src:ro,z" "$image" sh -c \
    "command -v python3 >/dev/null 2>&1 || { $install; } >/dev/null 2>&1; python3 /src/skills/linux-ops/scripts/detect_host.py --compact")"; then
    echo "FAIL: could not run the detector"
    failed=1
    continue
  fi
  echo "$profile"
  if ! EXPECT_FAMILY="$family" EXPECT_MANAGER="$manager" python3 -c '
import json, os, sys
profile = json.loads(sys.stdin.read())
expected = {
    "family": os.environ["EXPECT_FAMILY"],
    "package_manager": os.environ["EXPECT_MANAGER"],
    "support": "tier1",
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
