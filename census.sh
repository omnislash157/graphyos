#!/usr/bin/env bash
# census — where the private language sits in the tracked tree, per top-level directory, by the
# keyed scrub (scrub.py; the words never travel, and their digests are HMAC'd under .private_key,
# which never travels either). Exit 1 when any tracked file OUTSIDE staging/ carries one: that is
# the public cut's tripwire. A box without the key (CI) cannot run the sweep and says CENSUS SKIPPED.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
[ -s .private_key ] || { echo "CENSUS SKIPPED: no .private_key beside census.sh — the keyed sweep runs on the operator's box, never here"; exit 0; }
tracked="$(git ls-files)"
printf '%-22s %8s %8s\n' "directory" "tracked" "flagged"
total=0
for d in $(printf '%s\n' "$tracked" | awk -F/ '{print ($0 ~ /\//) ? $1 : "(root)"}' | sort -u); do
    if [ "$d" = "(root)" ]; then files="$(printf '%s\n' "$tracked" | grep -v '/' || true)"
    else files="$(printf '%s\n' "$tracked" | grep "^$d/" || true)"; fi
    n="$(printf '%s\n' "$files" | grep -c . || true)"
    flagged="$(printf '%s\n' "$files" | xargs -r python3 scrub.py 2>/dev/null | grep -c ': private token' || true)"
    printf '%-22s %8s %8s\n' "$d" "$n" "$flagged"
    total=$((total+flagged))
done
echo "flagged lines: $total across the tracked tree (the markers are keyed digests in .private_markers.sha256)"
python3 scrub.py --tracked > /dev/null 2>&1 \
    && echo "CENSUS OK: nothing tracked outside staging/ carries a private marker" \
    || { echo "CENSUS RED: private language outside staging/ — the public cut cannot be made:"; python3 scrub.py --tracked | grep ': private token' | sed 's/^/  /'; exit 1; }
