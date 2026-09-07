"""The workflow parse in the gate: a file GitHub cannot parse is refused with its line, without a
dependency. A floor; the gate runs the real one over .github/workflows."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("workflows", ROOT / "workflows.py")
workflows = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflows)

GOOD = """name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  floor:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: "the receipt (quick: the floor, the gate, the wheel)"
        run: |
          python -m venv .venv && .venv/bin/pip install -q -e "engine[dev]"   # not a comment
          python3 measure.py run --quick
      - name: the floor
        if: steps.x.outputs.url != ''
        run: cd engine && pytest -q
  gate:
    needs: floor
    runs-on: ubuntu-latest
    steps:
      - run: bash standalone_check.sh
"""


def test_GREEN_the_subset_parses_as_yaml_does():
    doc = workflows.parse(GOOD)
    assert list(doc) == ["name", "on", "jobs"]
    assert doc["on"] == {"push": {"branches": ["main"]}, "pull_request": None}
    steps = doc["jobs"]["floor"]["steps"]
    assert steps[1]["with"]["python-version"] == "${{ matrix.python-version }}"
    assert steps[2]["name"] == "the receipt (quick: the floor, the gate, the wheel)"
    assert steps[2]["run"] == ('python -m venv .venv && .venv/bin/pip install -q -e "engine[dev]"   # not a comment\n'
                               "python3 measure.py run --quick\n")
    assert steps[3]["if"] == "steps.x.outputs.url != ''"
    assert doc["jobs"]["floor"]["strategy"]["matrix"]["python-version"] == ["3.10", "3.12"]
    assert workflows.check_shape(doc) == []


def test_RED_an_unquoted_colon_in_a_step_name_is_refused_with_its_line():
    bad = GOOD.replace('- name: "the receipt (quick: the floor, the gate, the wheel)"',
                       "- name: the receipt (quick: the floor, the gate, the wheel)")
    with pytest.raises(workflows.WorkflowError) as exc:
        workflows.parse(bad)
    assert exc.value.line == 19 and "mapping values are not allowed here" in exc.value.why


@pytest.mark.parametrize("mutate, line, why", [
    (lambda t: t.replace("      - uses: actions/setup-python@v5", "        - uses: actions/setup-python@v5"), 16, "bad indentation"),
    (lambda t: t.replace("    runs-on: ubuntu-latest\n    strategy", "    runs-on: ubuntu-latest\n    runs-on: x\n    strategy"), 11, "duplicate key"),
    (lambda t: t.replace("\non:\n", "\n: x\non:\n"), 3, "not `key: value`"),
    (lambda t: t.replace("  push:", "\tpush:"), 4, "a tab in the indentation"),
    (lambda t: t.replace('["3.10", "3.12"]', '["3.10", "3.12'), 13, "unclosed"),
    (lambda t: t.replace("run: cd engine && pytest -q", "run: cd engine &&\n          pytest -q"), 26, "continues on the next line"),
])
def test_RED_each_fault_names_its_line(mutate, line, why):
    with pytest.raises(workflows.WorkflowError) as exc:
        workflows.parse(mutate(GOOD))
    assert exc.value.line == line, str(exc.value)
    assert why in exc.value.why, str(exc.value)


def test_RED_the_shape_names_what_github_would_refuse():
    doc = workflows.parse(GOOD)
    del doc["jobs"]["gate"]["runs-on"]
    doc["jobs"]["gate"]["needs"] = "nowhere"
    doc["jobs"]["floor"]["steps"][0] = {"name": "neither"}
    doc["jobs"]["floor"]["steps"][1]["bogus"] = "x"
    doc["extra"] = 1
    red = workflows.check_shape(doc)
    assert red == ["top-level key 'extra' is not one GitHub knows",
                   "job 'floor' step 1: a step carries exactly one of 'uses' and 'run'",
                   "job 'floor' step 2: key 'bogus' is not one GitHub knows",
                   "job 'gate' has no 'runs-on'",
                   "job 'gate' needs 'nowhere', which is not a job"]
    assert workflows.check_shape({"name": "x"}) == ["no top-level 'on'", "no top-level 'jobs'",
                                                    "'jobs' is not a mapping of at least one job"]


def test_GREEN_the_repo_workflows_and_RED_a_directory_with_the_fault(tmp_path):
    red, notes = workflows.check_dir(ROOT / ".github" / "workflows")
    assert red == [] and len(notes) >= 1
    (tmp_path / "ci.yml").write_text(GOOD.replace('- name: "the receipt (quick: the floor, the gate, the wheel)"',
                                                  "- name: the receipt (quick: the floor, the gate, the wheel)"))
    red, notes = workflows.check_dir(tmp_path)
    assert red == [f"{tmp_path / 'ci.yml'}:19: mapping values are not allowed here — the plain scalar "
                   "'the receipt (quick: the floor, the gate, the wheel)' carries ': '; quote it"]
    assert notes == ["ci.yml: unparseable"]
    assert workflows.check_dir(tmp_path / "nowhere")[0] == [f"{tmp_path / 'nowhere'}: no workflow file to parse"]


def test_GREEN_the_showcase_job_holds_no_token_and_no_checkout_and_the_post_job_is_separate():
    """The showcase runs a stranger's repo: its job carries no GH_TOKEN, checks out nothing, and
    may write nothing; the one job with issues: write only downloads the comment and posts it
    (graphyos #34)."""
    doc = workflows.parse((ROOT / ".github" / "workflows" / "showcase-on-issue.yml").read_text())
    jobs = doc["jobs"]
    show = [j for j in jobs.values() if any("graphy showcase" in (st.get("run") or "") for st in j["steps"])]
    assert len(show) == 1, "one job runs the showcase"
    show = show[0]
    assert "GH_TOKEN" not in str(show) and "github.token" not in str(show)
    assert not any("checkout" in (st.get("uses") or "") for st in show["steps"])
    assert show.get("permissions") == {} and doc.get("permissions") == {}
    post = [j for j in jobs.values() if any("issue comment" in (st.get("run") or "") for st in j["steps"])]
    assert len(post) == 1 and post[0] is not show and post[0]["needs"] == "showcase"
    assert post[0]["permissions"] == {"issues": "write"}
    assert not any("checkout" in (st.get("uses") or "") for st in post[0]["steps"])
    assert not any("grep" in (st.get("run") or "") and "the text:" in (st.get("run") or "") for st in show["steps"]), "the page path is grepped from the log"
