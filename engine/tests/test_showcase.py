"""The showcase page: composed from the store and the proposal, checked. A floor; the proof is the
three cold showcases in RECON."""
from __future__ import annotations

import json
import subprocess

import pytest
from pathlib import Path

import graphy.cli as cli
import graphy.federated_store as fs
import graphy.fanout as fanout
import graphy.pillars as pillars
import graphy.showcase as showcase
import graphy.sugiyama as sugi
from test_doors import _fixture


def test_GREEN_compose_writes_a_checked_page_and_text(tmp_path):
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    part = tmp_path / "partition.json"
    part.write_text(json.dumps({"groups": {"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]}, "rest": "EDGE"}))
    cut = fanout.load_partition(part)
    proposal = pillars.Proposal(corpus="fastapi", depth=2, floor=5, owned=2 / 3, client=1 / 3, rest="EDGE",
                                crowns={"ROUTING": "fastapi.routing", "DEPS": "fastapi.dependencies"}, floor_arm=None,
                                arms={"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]},
                                rulings=[pillars.Ruling(unit="fastapi.routing", arm="ROUTING", role="orchestrator", fan_in=1, fan_out=9, how="crown")],
                                total=10)
    ring = {"root": "fastapi", "minted": {"fastapi": {}, "widgets": {}}, "unresolved": {"brotli": "not under x"}}
    html, text = showcase.compose(store, package="fastapi", desc=desc, home=tmp_path, proposal=proposal, cut=cut, ring=ring,
                                  graphy_cmd=["graphy"], origin="https://example.invalid/fastapi.git")
    page = tmp_path / "index.html"
    page.write_text(html, encoding="utf-8")
    assert sugi.check_artifact(page) == []
    assert '&quot;mcpServers&quot;' in html and "graphy blast fastapi.routing" in html and "widgets" in html and "brotli" in html
    assert "https://" not in html.replace("https://example.invalid/fastapi.git", "")
    assert text.startswith("fastapi — drawn by graphy in one command") and "ADD YOUR MODEL" in text and "ASK IT" in text
    assert "THE PILLARS" in text and "ROUTING" in text


def test_RED_showcase_refusals(tmp_path, capsys):
    rc = cli.main(["showcase"])
    assert rc == 2 and "name a git url or a repo path" in capsys.readouterr().err
    rc = cli.main(["showcase", str(tmp_path / "nowhere")])
    assert rc == 2 and "not a directory" in capsys.readouterr().err


def test_GREEN_showcase_hands_no_provision_to_the_eat(tmp_path, monkeypatch):
    """`showcase --no-provision` eats with the flag, so nothing of the stranger's repo runs on
    the box that showcases it (graphyos #35): the argv the eat receives is pinned."""
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv: (seen.append(argv), 2)[1])
    repo = tmp_path / "r"
    repo.mkdir()
    try:
        showcase.showcase(str(repo), no_provision=True)
    except showcase.ShowcaseError as exc:
        assert "eat exited 2" in str(exc)
    assert seen == [["eat", str(repo), "--no-provision"]]
    seen.clear()
    try:
        showcase.showcase(str(repo))
    except showcase.ShowcaseError:
        pass
    assert seen == [["eat", str(repo)]]


def test_GREEN_showcase_re_eats_a_dirty_working_tree(tmp_path, monkeypatch):
    """graphyos #39: a `.graphy` whose cursor still matches the tree is reused; one behind an
    uncommitted edit is eaten again — never a stale page in 0.0 s over a green audit."""
    import json
    import subprocess
    from graphy import cartograph as carto
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv: (seen.append(argv), 2)[1])
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.py").write_text("def a():\n    return 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "i"], cwd=repo, check=True)
    home = repo / ".graphy"
    home.mkdir()
    (home / ".gitignore").write_text("*\n")
    cursor, _ = carto.repo_cursor(repo, exclude=(home,))
    (home / "tenant.json").write_text(json.dumps({"cursor": cursor}))
    try:
        showcase.showcase(str(repo))
    except (showcase.ShowcaseError, OSError):
        pass
    assert seen == [], "a current .graphy was eaten again"
    (repo / "a.py").write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    logged = []
    try:
        showcase.showcase(str(repo), log=logged.append)
    except showcase.ShowcaseError as exc:
        assert "eat exited 2" in str(exc)
    assert seen == [["eat", str(repo)]]
    assert any("the working tree moved past the store: 1 file(s)" in line and "eating again" in line for line in logged)


def _hostile_proposal():
    """Arms and crowns named with backticks: the module names a producer prints are not slug-checked."""
    return pillars.Proposal(corpus="fastapi", depth=2, floor=5, owned=2 / 3, client=1 / 3, rest="EDGE",
                            crowns={"```": "fastapi.routing", "````.ts": "fastapi.dependencies"}, floor_arm=None,
                            arms={"```": ["fastapi.routing"], "````.ts": ["fastapi.dependencies"]},
                            rulings=[pillars.Ruling(unit="fastapi.routing", arm="```", role="orchestrator", fan_in=1, fan_out=9, how="crown")],
                            total=10)


def test_GREEN_the_text_page_is_written_for_the_fence(tmp_path):
    """A module or arm named with backticks is printed verbatim into showcase.txt, which the workflow
    posts inside a fence; a line of three or more backticks (up to three spaces in) closes a fence
    and the rest of the name injects Markdown into a bot-authored comment (graphyos #40). Every such
    line is backslash-escaped, visibly; every other line is untouched."""
    fs_ = showcase.fence_safe
    assert fs_("```") == "\\`\\`\\`" and fs_("  ````.ts") == "  \\`\\`\\`\\`.ts" and fs_("   `````  ") == "   \\`\\`\\`\\`\\`  "
    assert fs_("    ```") == "    ```", "four spaces in is code, never a fence"
    assert fs_("x```") == "x```" and fs_("``") == "``" and fs_("~~~") == "~~~" and fs_("plain") == "plain"
    assert fs_("a\n```\nb") == "a\n\\`\\`\\`\nb" and fs_("") == ""
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    part = tmp_path / "partition.json"
    part.write_text(json.dumps({"groups": {"```": ["fastapi.routing"], "````.ts": ["fastapi.dependencies"]}, "rest": "EDGE"}))
    html, text = showcase.compose(store, package="fastapi", desc=desc, home=tmp_path, proposal=_hostile_proposal(), cut=fanout.load_partition(part),
                                  ring={"root": "fastapi", "minted": {"fastapi": {}}, "unresolved": {}}, graphy_cmd=["graphy"], origin="````")
    closing = [ln for ln in text.splitlines() if showcase._FENCE_LINE.match(ln)]
    assert closing == [], f"showcase.txt carries a line that closes a fence: {closing!r}"
    assert "  \\`\\`\\`\\`" in text and "\\`\\`\\`            crown fastapi.routing" in text, "the names are escaped, not dropped"
    assert "```" in html and "\\`" not in html, "the html page escapes for html, never for a fence"
    page = tmp_path / "index.html"
    page.write_text(html, encoding="utf-8")
    assert sugi.check_artifact(page) == []


def test_GREEN_the_comment_fence_is_longer_than_any_backtick_run_the_body_carries(tmp_path):
    """The workflow's comment step computes its fence from the body it posts — the page or the
    refusal lines — one backtick longer than the longest run inside, never a fixed four; the step
    is run here, as bash, against a body built to close a four-backtick fence (graphyos #40)."""
    import re
    import subprocess
    from test_workflows import ROOT, workflows as wf
    src = (ROOT / ".github" / "workflows" / "showcase-on-issue.yml").read_text()
    doc = wf.parse(src)
    step = next(st for j in doc["jobs"].values() for st in j["steps"] if "comment.md" in (st.get("run") or ""))
    run = step["run"]
    assert "'````text'" not in run and "echo '````'" not in run, "the fence is fixed at four backticks"
    assert "grep -oE '`+'" in run and "${fence}text" in run and 'echo "$fence"' in run
    body = "x\n`````\n  \\`\\`\\`\nend"                       # a five-run: the old fence of four opens a new block
    for rc, log in ((0, ""), (2, "SHOWCASE REFUSED: ``````` seven\n")):
        home = tmp_path / f"rc{rc}"
        (home / "page").mkdir(parents=True)                # the page lands at --out, never at the clone (graphyos #58)
        (home / "page" / "showcase.txt").write_text(body)
        (home / "showcase.log").write_text(log)
        script = run[run.index('page="$RUNNER_TEMP'):]
        proc = subprocess.run(["bash", "-c", script], env={"PATH": "/usr/bin:/bin", "RUNNER_TEMP": str(home),
                                                            "URL": "https://example.invalid/x", "rc": str(rc)}, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        comment = (home / "comment.md").read_text()
        posted = body if rc == 0 else log.rstrip("\n")
        longest = max(len(m) for m in re.findall(r"`+", posted))
        fence = "`" * (longest + 1)
        assert comment.endswith(f"\n{fence}text\n{posted}\n{fence}\n"), comment
        assert "\n" + fence + "`" not in comment, "a longer run than the fence is inside the body"
        assert ("It refused" in comment) == (rc != 0)


def test_RED_showcase_without_work_says_where_the_clone_lands(tmp_path, monkeypatch):
    """A url with no --work clones under ./showcase in the current directory; the run says so
    before the clone, and names the reuse when the clone already stands (graphyos #43)."""
    monkeypatch.chdir(tmp_path)
    logged = []
    calls = []

    def fake_run(argv, **kw):
        if argv[:2] == ["git", "-C"]:                 # the reuse reads the clone's origin (graphyos #58)
            return subprocess.CompletedProcess(argv, 0, "https://example.invalid/o/thing.git\n", "")
        calls.append(argv)
        repo = Path(argv[-1])
        (repo / ".git").mkdir(parents=True)
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(showcase.subprocess, "run", fake_run)
    with pytest.raises(showcase.ShowcaseError):        # the clone stands, then the eat refuses an empty repo
        showcase.showcase("https://example.invalid/o/thing.git", log=logged.append, no_provision=True)
    where = str((tmp_path / "showcase").resolve())
    assert any(line.startswith("SHOWCASE: no --work") and where in line and "--work <dir>" in line for line in logged), logged
    assert calls and calls[0][-1] == str(tmp_path / "showcase" / "o" / "thing")   # keyed on owner and name
    logged.clear()
    with pytest.raises(showcase.ShowcaseError):
        showcase.showcase("https://example.invalid/o/thing.git", log=logged.append, no_provision=True)
    assert any(line.startswith("SHOWCASE: reusing the clone at") and line.endswith("o/thing") for line in logged), logged
    assert len(calls) == 1


def test_GREEN_repo_of_and_clone_dir_key_on_owner_and_name(tmp_path):
    """One parse for the clone key and the gallery's slug (graphyos #58): `.git` and a trailing slash fold,
    two repos of one name land in two directories, a url with no owner/name tail refuses."""
    assert showcase.repo_of("https://github.com/pallets/click.git") == ("pallets", "click")
    assert showcase.repo_of("https://gitlab.com/Some-Org/My.Repo/") == ("Some-Org", "My.Repo")
    assert showcase.repo_of("git@github.com:pallets/click.git") == ("pallets", "click")
    assert showcase.clone_dir(tmp_path, "https://github.com/pallets/click") == tmp_path / "pallets" / "click"
    assert showcase.clone_dir(tmp_path, "https://github.com/some-fork/click.git") == tmp_path / "some-fork" / "click"
    # a GitLab group path is the whole owner: two groups' `tools/repo` are two directories
    assert showcase.repo_of("https://gitlab.com/groupA/tools/repo.git") == ("groupA/tools", "repo")
    assert showcase.clone_dir(tmp_path, "https://gitlab.com/groupB/tools/repo") == tmp_path / "groupB" / "tools" / "repo"
    assert showcase.repo_of("https://git.sr.ht/~sircmpwn/aerc") == ("~sircmpwn", "aerc")
    assert showcase.repo_of("https://x-access-token:abc@github.com/pallets/click") == ("pallets", "click")
    for bad in ("https://github.com/click", "https://github.com/", "click", "https://git.example.com/click.git",
                "https://github.com/pallets/..", "https://github.com/../..", "https://github.com/pallets/.git",
                "https://github.com/./click", "https://github.com/pallets/click?x#y"):
        with pytest.raises(showcase.ShowcaseError, match="not an <owner>/<name> git url"):
            showcase.repo_of(bad)
    # the same repo under two spellings is one repo; a token never travels in a message
    assert showcase._same_repo("git@github.com:pallets/click.git", "https://github.com/pallets/click")
    assert showcase._same_repo("https://x-access-token:abc@GitHub.com/pallets/click", "https://github.com/pallets/click/")
    assert not showcase._same_repo("https://github.com/pallets/click", "https://github.com/some-fork/click")
    assert not showcase._same_repo("", "https://github.com/pallets/click")
    assert showcase._shown("https://x-access-token:abc@github.com/pallets/click") == "https://github.com/pallets/click"


def test_RED_showcase_refuses_a_standing_clone_of_another_repo(tmp_path):
    """A directory under --work that is a clone of another url is never reused (graphyos #58): the
    origin read from the clone itself decides, and the refusal names both. Proven on a real git."""
    src = tmp_path / "src"
    subprocess.run(["git", "init", "-q", str(src)], check=True)
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(src), "-c", "user.email=a@b", "-c", "user.name=a", "add", "."], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "one"], check=True)
    work = tmp_path / "work"
    stands = showcase.clone_dir(work, "https://github.com/some-fork/click.git")
    subprocess.run(["git", "clone", "-q", str(src), str(stands)], check=True)   # git makes the owner dir
    logged = []
    with pytest.raises(showcase.ShowcaseError) as exc:
        showcase._clone("https://github.com/some-fork/click.git", work, logged.append)
    assert str(exc.value) == f"{stands} is a clone of {src}, not https://github.com/some-fork/click.git"
    assert not logged
    # the same repo, spelled with or without .git or a trailing slash, is the clone it stands for
    assert showcase._clone(f"{src}/", work.parent / "w2", logged.append) == showcase.clone_dir(work.parent / "w2", str(src))
    assert showcase._clone(str(src), work.parent / "w2", logged.append) == showcase.clone_dir(work.parent / "w2", str(src))
    assert any(line.startswith("SHOWCASE: reusing the clone at") for line in logged), logged


def test_RED_showcase_names_git_refusing_to_read_a_standing_clone(tmp_path, monkeypatch):
    """A `.git` that stands but git cannot open (dubious ownership, a corrupt config) is git's reason,
    never `<no origin>` (graphyos #58)."""
    work = tmp_path / "w"
    stands = showcase.clone_dir(work, "https://github.com/pallets/click.git")
    (stands / ".git").mkdir(parents=True)

    def fake_run(argv, **kw):
        assert argv[:2] == ["git", "-C"]
        return subprocess.CompletedProcess(argv, 128, "", "fatal: detected dubious ownership in repository")
    monkeypatch.setattr(showcase.subprocess, "run", fake_run)
    with pytest.raises(showcase.ShowcaseError, match="stands but git cannot read it: fatal: detected dubious ownership"):
        showcase._clone("https://github.com/pallets/click.git", work, lambda *_: None)


def test_RED_showcase_non_dotted_partition_refuses_on_one_line_never_a_stack(tmp_path, capsys, monkeypatch):
    """A module named outside the dotted identifier eats green and the showcase must still end on one
    line (graphyos #46): a FanoutError or a PillarsError under the showcase is `SHOWCASE REFUSED: …`,
    exit 2 — the classes the verb did not catch before."""
    def boom(*a, **k):
        raise fanout.FanoutError("partition at p: group 'HOSTILE' carries a non-dotted prefix 'hostile.```'")
    monkeypatch.setattr(showcase, "showcase", boom)
    rc = cli.main(["showcase", str(tmp_path), "--no-provision"])
    err = capsys.readouterr().err
    assert rc == 2 and err.splitlines() == ["SHOWCASE REFUSED: partition at p: group 'HOSTILE' carries a non-dotted prefix 'hostile.```'"]

    def boom2(*a, **k):
        raise pillars.PillarsError("corpus 'x' has no module graph")
    monkeypatch.setattr(showcase, "showcase", boom2)
    rc = cli.main(["showcase", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 2 and err.splitlines() == ["SHOWCASE REFUSED: corpus 'x' has no module graph"]


def test_GREEN_showcase_nondotted_proposal_round_trips_through_the_partition(tmp_path):
    """The proposal writes the walk's unit names as prefixes; a unit named `hostile.```` (a
    TypeScript module ```.ts) loads back and cuts by exact prefix, its arm named ARM (graphyos #46)."""
    units = ["hostile", "hostile.```", "hostile.other"]
    proposal = pillars.Proposal(corpus="hostile", depth=2, floor=5, owned=2 / 3, client=1 / 3, rest="EDGE",
                                crowns={"HOSTILE": "hostile"}, floor_arm=None, arms={"HOSTILE": units},
                                rulings=[], total=0)
    partition = tmp_path / "partition.json"
    pillars.write_partition(partition, pillars.to_partition(proposal))
    cut = fanout.load_partition(partition)
    assert cut.group_of("hostile.```") == "HOSTILE" and cut.group_of("hostile.```.f") == "HOSTILE"
    assert cut.group_of("hostile.other.c") == "HOSTILE" and cut.group_of("zod") == "EDGE"
