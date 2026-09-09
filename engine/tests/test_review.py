"""The review battery's floor: every check goes red on its seeded fixture and green on the fixed one;
a check that cannot run refuses instead of reporting a clean zero; the command tokenizer reads a
placeholder as the reader's value and never as a flag. The gate runs the real battery over the tree."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("review", Path(__file__).parents[2] / "review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_GREEN_every_check_is_red_on_its_fixture_and_green_on_the_fixed_one():
    rows = review.selftest()
    assert len(rows) == len(review.fixtures()) >= 8
    for check, red, green in rows:
        assert red >= 1, f"{check} does not go red on its own fixture — decoration, not a check"
        assert green == 0, f"{check} reports {green} finding(s) on its fixed fixture"


def test_RED_a_check_that_cannot_run_refuses_instead_of_a_clean_zero(tmp_path):
    root = review._seed({"README.md": "no command here\n"})
    with pytest.raises(review.CheckError, match="ZERO commands"):
        review.check_advertised_argv(root)
    with pytest.raises(review.CheckError, match="CLAUDE.md is absent"):
        review.check_paths(root)
    with pytest.raises(review.CheckError, match="RECON.md is absent"):
        review.check_sha_liveness(root)


def test_GREEN_placeholders_and_brackets_are_values_and_a_comment_is_not_a_command():
    toks = review._tokens("--tenant <descriptor> --tenant-id <name> [--sessions <abs>] [--check \\| --release <v>] … | tail -1")
    assert toks == ["--tenant", "<descriptor>", "--tenant-id", "<name>", "--sessions", "<abs>", "--check", "--release", "<v>"]
    assert review._uncommented("graphy check --tenant t.json   # then `graphy walk --nope`") == "graphy check --tenant t.json  "
    lines = list(review._command_lines("```text\nthe graphy tenant's picture\ngraphy check --tenant t\n```\nrun `graphy walk --seed a`\n", 1))
    assert lines == [(3, "graphy check --tenant t"), (5, "graphy walk --seed a")]


def test_GREEN_the_verbs_come_from_the_engines_own_parser():
    verbs = review._verbs()
    assert {"eat", "walk", "check", "history", "review"} - set(verbs) == {"review"}
    assert "--tenant-id" in verbs["walk"] and "--replay" in verbs["traversals"] and "--with" in verbs["history"]


def test_GREEN_a_page_keeps_its_colours_in_the_token_block_and_binds_its_hooks(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(review._PAGE_OK.replace("{script}", ""), encoding="utf-8")
    assert review.page_findings(page, "p.html") == []
    page.write_text(review._PAGE_OK.replace("{script}", '<script>var s = document.querySelector("#ghost"); '
                                            'document.querySelectorAll(".may-be-empty");</script>')
                    .replace('<svg viewBox', '<svg data-interactive="1" viewBox'), encoding="utf-8")
    what = [f.what for f in review.page_findings(page, "p.html")]
    assert what == ["the script hooks '#ghost' and the page has no such element"]
    page.write_text(review._PAGE_OK.replace("{script}", "").replace(".node rect { fill: var(--paper); }", ".node rect { fill: rgb(1,2,3); }"), encoding="utf-8")
    assert any("colour literal outside the token block" in f.what for f in review.page_findings(page, "p.html"))


def test_GREEN_severance_names_the_reader_through_its_import_and_a_move_is_a_deletion(tmp_path):
    root = review._seed({"engine/graphy/a.py": "class K:\n    def close(self):\n        pass\n",
                         "engine/graphy/b.py": "from graphy import a\na.K().close()\n",
                         "engine/graphy/c.py": "from graphy.a import K\nK()\nimport sqlite3\nsqlite3.connect(':memory:').close()\n",
                         "engine/graphy/d.py": "from graphy.a import K\nK().close()\n"})
    (root / "engine/graphy/a.py").write_text("class K:\n    pass\n", encoding="utf-8")
    found = review.check_severance(root, "HEAD")
    assert [(f.where, f.what.split(",")[0]) for f in found] == [("engine/graphy/b.py", "still names graphy.a.K.close"),
                                                               ("engine/graphy/d.py", "still names graphy.a.K.close")]
    # a move: git reports a rename; the old module's readers are severed all the same
    (root / "engine/graphy/a.py").write_text("class K:\n    def close(self):\n        pass\n", encoding="utf-8")
    review._fixture_git(root, ["git", "mv", "engine/graphy/a.py", "engine/graphy/a2.py"])
    moved = review.check_severance(root, "HEAD")
    assert {f.where for f in moved} == {"engine/graphy/b.py", "engine/graphy/c.py", "engine/graphy/d.py"}
