#!/usr/bin/env bash
# Run everything .github/workflows/ci.yml runs, locally.
#
# Keep it in step with the workflow: if you add a CI step there, add it here.
#
# Usage: tools/ci-local.sh          (from the repo root)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# An unparseable workflow fails at startup with zero jobs, so CI reports
# nothing and every PR still looks green (PKC #82). A workflow cannot check
# itself, so this runs before the push. `assert fs` keeps a deleted workflow
# from passing vacuously.
python3 -c "import glob,yaml; fs=sorted(glob.glob('.github/workflows/*.yml')); assert fs, 'no workflows found'; [yaml.safe_load(open(f)) for f in fs]"

python3 -m py_compile scripts/rkc_*.py

python3 tests/test_plugin.py
python3 tests/test_rkc.py
python3 tests/test_extract.py
python3 tests/test_bulk_fixes.py
python3 tests/test_spine.py
python3 tests/test_search.py

python3 scripts/rkc_validate.py --root sample-knowledge --spine

SUBJECT=subject.loop-policy.01J8X000000000000000000001
python3 scripts/rkc_pack.py "$SUBJECT" --root sample-knowledge > "$TMP/pack.json"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); ids={n['id'] for n in d['nodes']}; types={n['type'] for n in d['nodes']}; assert 'Claim' in types and 'Evidence' in types, d; assert 'claim.loop-policy.01J8X000000000000000000006' in ids" "$TMP/pack.json"
python3 scripts/rkc_pack.py "$SUBJECT" --root sample-knowledge --summary > "$TMP/pack-summary.md"
grep -q "Pack summary" "$TMP/pack-summary.md"
grep -q "Finding=" "$TMP/pack-summary.md"

python3 scripts/rkc_search.py "false civic alerts" --root sample-knowledge --engine scan --json > "$TMP/search.json"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['count']>=1, d; types={r['type'] for r in d['results']}; assert 'Finding' in types or 'ResearchQuestion' in types, d" "$TMP/search.json"

python3 scripts/rkc_segment.py sample-knowledge/research/source-assets/3134869d568209bfb387f9a6b8eeada1e0596b64e90460b623fa58e187f77169/original.md

echo "CI OK"
