#!/usr/bin/env bash
# sync_public — the public cut, kept current: every tracked file outside staging/ (and the skills)
# copied into the public checkout, URLs repointed, scrubbed and gated there, committed and pushed.
# The private repo is the archive that also holds staging/; the public one is what ships.
#   bash sync_public.sh [<public checkout>]        default ../graphyos
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUB="${1:-$HERE/../graphyos}"
[ -d "$PUB/.git" ] || { echo "SYNC REFUSED: no public checkout at $PUB (git clone https://github.com/omnislash157/graphyos.git)" >&2; exit 2; }
cd "$HERE"
git ls-files | grep -v '^staging/' | grep -v '^.claude/skills/' > "$PUB/.sync_manifest"
# retire what the private tree no longer tracks (never the public repo's own .git or gitignored state)
( cd "$PUB" && git ls-files | grep -vxFf .sync_manifest | grep -v '^.sync_manifest$' | xargs -r git rm -q -- ) || true
while read -r f; do mkdir -p "$PUB/$(dirname "$f")"; cp "$f" "$PUB/$f"; done < "$PUB/.sync_manifest"
rm -f "$PUB/.sync_manifest"
cd "$PUB"
sed -i 's#omnislash157/graphy\.git && cd graphy#omnislash157/graphyos.git \&\& cd graphyos#; s#omnislash157/graphy/actions#omnislash157/graphyos/actions#g' README.md
sed -i 's#omnislash157/graphy\b#omnislash157/graphyos#g' CLAUDE.md RECON.md .claude/hooks/march.py
sed -i 's#^staging/docs/         doctrine and prior audits — development input, never released$#staging/              gitignored — the corpora, the indexes and the farm work this box minted from; never tracked#; /^staging\/tools\/  /d; /^staging\/skills\/  /d; /^staging\/containers\/ /d; /^staging\/brains\/  /d; /^staging\/corpora\/  /d' CLAUDE.md
python3 scrub.py --tracked | tail -1
bash release.sh --check
git add -A
if git diff --cached --quiet; then echo "SYNC OK: the public cut is current"; exit 0; fi
MSG="${SYNC_MESSAGE:-$(cd "$HERE" && git log -1 --format=%s)}"
git -c user.name="$(cd "$HERE" && git log -1 --format=%an)" -c user.email="$(cd "$HERE" && git log -1 --format=%ae)" commit -q -m "$MSG"
git push -q origin main
echo "SYNC OK: $(git rev-parse --short HEAD) pushed to $(git remote get-url origin)"
