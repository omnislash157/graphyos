"""The farm: many packages into one index, resumably, every verdict in the receipt. A floor with
PyPI and pip injected — the proof is the top-N run in RECON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.cli as cli
import graphy.farm as farm
import graphy.index as shard_index

PYPI = {
    "six": {"releases": {"1.16.0": [{"size": 11000}], "1.17.0": [{"size": 11500}], "2.0.0a1": [{"size": 100}]}},
    "biggie": {"releases": {"3.0": [{"size": 900_000_000}]}},
    "empty": {"releases": {"0.1": [{"size": 1000}]}},
    "two-names": {"releases": {"2.0": [{"size": 5000}]}},
}
TOP = {"rows": [{"project": "six"}, {"project": "biggie"}, {"project": "empty"}, {"project": "two-names"}]}


def _fetch(url: str) -> dict:
    if url == farm.TOP_URL:
        return TOP
    name = url.rsplit("/", 2)[-2]
    if name not in PYPI:
        raise OSError(f"404 {url}")
    return PYPI[name]


def _provision(venv: Path, distribution: str, release: str) -> Path:
    """A site-packages holding what `pip install --no-deps distribution==release` would: a dist-info
    with RECORD, and the package's source."""
    sp = venv / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True)
    modules = {"six": ["six"], "empty": [], "two-names": ["two_names", "tn_compat"]}[distribution]
    info = sp / f"{distribution.replace('-', '_')}-{release}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Name: {distribution}\nVersion: {release}\nLicense: MIT\n")
    records = []
    for m in modules:
        (sp / m).mkdir()
        (sp / m / "__init__.py").write_text(f"import os\n\ndef hello():\n    return os.getcwd()\n")
        records.append(f"{m}/__init__.py,,")
    (info / "RECORD").write_text("\n".join(records) + "\n")
    return sp


def test_GREEN_farm_mints_skips_refuses_and_resumes(tmp_path):
    index, work = tmp_path / "index", tmp_path / "work"
    specs = farm.top_packages(4, fetch=_fetch)
    assert specs == ["six", "biggie", "empty", "two-names"]
    lines = []
    r = farm.farm(specs, index=index, work=work, jobs=4, python="python3", fetch=_fetch, provision=_provision,
                  max_wheel_mb=100, log=lines.append)
    p = r["packages"]
    assert p["six==1.17.0"]["state"] == "minted"                       # the newest final, not the pre-release
    assert p["biggie==3.0"]["state"] == "refused" and "over the 100 MB cap" in p["biggie==3.0"]["reason"]
    assert p["empty==0.1"]["state"] == "refused" and "installs no importable package" in p["empty==0.1"]["reason"]
    two = p["two-names==2.0"]
    assert two["state"] == "minted" and [s["name"] for s in two["shards"]] == ["two-names==2.0", "two-names==2.0@tn_compat"]
    assert two["unresolved"] == {"os": "the ring is the index"}
    assert r["totals"] == {"minted": 2, "skipped": 0, "refused": 2, "shards_new": 3, "shards_exist": 0,
                           "seconds": r["totals"]["seconds"]}
    cat = shard_index.catalog(str(index))
    assert set(cat) == {"six==1.17.0", "two-names==2.0", "two-names==2.0@tn_compat"}
    assert not (work / "six" / "venv").exists()                        # the venv is deleted after the mint
    assert json.loads((work / farm.RECEIPT_NAME).read_text())["totals"]["minted"] == 2
    assert any(l.startswith("FARM REFUSED: biggie==3.0") for l in lines)
    # resume: pinned names the index holds are skipped by address; the rest run again and land as `exists`
    r2 = farm.farm(["six==1.17.0", "two-names"], index=index, work=work, jobs=1, python="python3", fetch=_fetch,
                   provision=_provision, log=lines.append)
    assert r2["packages"]["six==1.17.0"]["state"] == "skipped"                 # pinned: skipped before any work
    assert r2["packages"]["two-names==2.0"]["state"] == "skipped"            # unpinned: PyPI named the release the index holds
    assert r2["totals"]["skipped"] == 2 and r2["totals"]["minted"] == 0
    # --force re-mints: a new PROVENANCE (its minted_at) is a new address, and the name is repointed
    r3 = farm.farm(["two-names"], index=index, work=work, jobs=1, python="python3", fetch=_fetch,
                   provision=_provision, force=True)
    assert r3["packages"]["two-names==2.0"]["state"] == "minted" and len(r3["packages"]["two-names==2.0"]["shards_pushed"]) == 2
    assert shard_index.verify_index(str(index)) and all(v[2] is None for v in shard_index.verify_index(str(index)))


def test_RED_select_release_and_cli_refusals(tmp_path, capsys):
    assert farm.select_release("six", None, max_wheel_mb=1, fetch=_fetch) == ("1.17.0", 0.0115)
    with pytest.raises(farm.FarmError, match="over the 1 MB cap"):
        farm.select_release("biggie", None, max_wheel_mb=1, fetch=_fetch)
    assert farm.select_release("biggie", "3.0", max_wheel_mb=None, fetch=_fetch)[0] == "3.0"
    assert farm.Spec.parse("Foo==1.2").name == "Foo==1.2" and farm.Spec.parse("foo").name is None
    assert farm.normalize("Typing_Extensions") == "typing-extensions"
    rc = cli.main(["farm", "--index", str(tmp_path / "i")])
    assert rc == 2 and "--index and --work are required" in capsys.readouterr().err
    rc = cli.main(["farm", "--index", str(tmp_path / "i"), "--work", str(tmp_path / "w")])
    assert rc == 2 and "exactly one of --top N or --packages" in capsys.readouterr().err


NPM_MD = "# Top 4 most dependent upon packages\n\n0. [left-pad](https://www.npmjs.org/package/left-pad) - 5\n1. [@acme/big](x) - 4\n2. [tiny](https://www.npmjs.org/package/tiny) - 3\n3. [gone](x) - 1\n\n# Top 1 packages with most dependencies\n\n0. [junk](x) - 99\n"
NPM = {
    "left-pad": {"dist-tags": {"latest": "1.3.0"}, "versions": {"1.3.0": {"dist": {"unpackedSize": 4000}, "license": "WTFPL"}}},
    "tiny": {"dist-tags": {"latest": "0.2.0"}, "versions": {"0.2.0": {"dist": {"unpackedSize": 900_000_000}}}},
    "gone": {"dist-tags": {}, "versions": {}},
}


def _npm_fetch(url: str) -> dict:
    if url.startswith(farm.NPM_DOWNLOADS_URL.split("{")[0]):
        names = url.rsplit("/", 1)[-1].split(",")
        return {n: {"downloads": {"left-pad": 10, "tiny": 50, "gone": 1}.get(n, 0), "package": n} for n in names}
    name = url.rsplit("/", 1)[-1]
    if name not in NPM:
        raise OSError(f"404 {url}")
    return NPM[name]


def _npm_provision(job: Path, distribution: str, release: str) -> Path:
    nm = job / "node_modules" / distribution
    nm.mkdir(parents=True)
    (nm / "package.json").write_text(json.dumps({"name": distribution, "version": release, "license": "MIT", "main": "index.js"}))
    (nm / "index.js").write_text("const util = require('util');\nmodule.exports = function leftPad(s, n) { return util.format(s); };\n")
    return job / "node_modules"


def test_GREEN_npm_farm_ranks_by_downloads_and_mints_javascript(tmp_path):
    pytest.importorskip("tree_sitter_typescript")
    specs = farm.top_packages(3, producer="typescript_ast", fetch=_npm_fetch, fetch_text=lambda _u: NPM_MD)
    assert specs == ["tiny", "left-pad", "gone"]                     # scoped names skipped, downloads decide
    r = farm.farm(specs, index=tmp_path / "index", work=tmp_path / "work", jobs=1, python="python3",
                  producer="typescript_ast", fetch=_npm_fetch, provision=_npm_provision, max_wheel_mb=100)
    p = r["packages"]
    assert p["left_pad==1.3.0"]["state"] == "minted" and p["left_pad==1.3.0"]["shards"][0]["name"] == "left_pad==1.3.0"
    assert p["tiny==0.2.0"]["state"] == "refused" and "over the 100 MB cap" in p["tiny==0.2.0"]["reason"]
    assert p["gone"]["state"] == "refused" and "lists no version" in p["gone"]["reason"]
    assert set(shard_index.catalog(str(tmp_path / "index"))) == {"left_pad==1.3.0"}
    assert p["left_pad==1.3.0"]["unresolved"] == {"util": "the ring is the index"}
