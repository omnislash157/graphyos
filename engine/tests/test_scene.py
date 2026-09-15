"""The atlas weights come from declared dependencies, including in a capped symbol view."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import pytest

from graphy.draw import DrawError
from graphy.fanout import Cut
from graphy.scene import emit_page, scene
from graphy.ir import DEPENDS, LEXICAL


class AtlasStore:
    relations = {"calls": [DEPENDS], "references": [DEPENDS], "mentions": [LEXICAL]}

    def owned(self, corpus):
        for dotted in ("pkg.app.run", "pkg.app.more", "pkg.core.work", "pkg.core.helper", "pkg.util.idle", "pkg.tests.test"):
            yield dotted, {"module": dotted.rsplit(".", 1)[0], "dotted": dotted, "node_type": "func",
                           "file": dotted.rsplit(".", 1)[0].replace(".", "/") + ".py", "line": 4,
                           "role": "test" if ".tests." in dotted else "definition"}

    def edges(self):
        return iter([
            ("pkg.app.run", "pkg.core.work", "calls"),
            ("pkg.app.run", "pkg.core.work", "calls"),  # duplicate corpus row must not inflate a path
            ("pkg.app.run", "pkg.core.work", "references"),
            ("pkg.app.more", "pkg.core.work", "calls"),
            ("pkg.core.work", "pkg.core.helper", "calls"),
            ("pkg.app.run", "pkg.app.more", "contains"),
            ("pkg.app.run", "pkg.core.helper", "mentions"),
            ("pkg.tests.test", "pkg.core.work", "calls"),
            ("pkg.app.run", "external.symbol", "calls"),
            ("pkg.app.run", "pkg.app.run", "calls"),
        ])


def atlas(max_nodes=3000):
    return scene(AtlasStore(), "pkg", Cut(groups={"APP": ["pkg.app"], "CORE": ["pkg.core"]}, rest="EDGE"),
                 max_nodes=max_nodes)


def test_overview_counts_real_dependencies_and_preserves_isolated_modules():
    sc = atlas()
    assert sc["counts"]["nodes"] == 5
    assert sc["counts"]["dependencies"] == 4
    assert sc["overview"]["links"] == [{"source": "pkg.app", "target": "pkg.core", "weight": 3, "kind": "cross"}]
    modules = {n["id"]: n for n in sc["overview"]["nodes"]}
    assert set(modules) == {"pkg.app", "pkg.core", "pkg.util"}
    assert modules["pkg.core"]["fanIn"] == 3
    assert modules["pkg.core"]["internal"] == 1
    assert modules["pkg.core"]["size"] == 2
    assert modules["pkg.app"]["fanOut"] == 3
    assert modules["pkg.util"]["fanIn"] == modules["pkg.util"]["fanOut"] == 0
    symbols = {n["id"]: n for n in sc["nodes"]}
    assert symbols["pkg.core.work"]["fanIn"] == 3
    assert symbols["pkg.core.work"]["fanOut"] == 1
    assert symbols["pkg.core.work"]["where"] == "pkg/core.py:4"
    assert next(l for l in sc["links"] if l["source"] == "pkg.app.run" and l["target"] == "pkg.core.work")["weight"] == 2
    assert sum(l["weight"] for l in sc["links"] if l["kind"] != "contains") == 4


def test_symbol_cap_keeps_overview_and_full_counts():
    full, capped = atlas(), atlas(max_nodes=1)
    assert capped["overview"] == full["overview"]
    assert capped["counts"]["shown"] == 1 and capped["counts"]["nodes"] == 5
    assert capped["nodes"][0]["id"] == "pkg.core.work"
    assert capped["links"] == []
    assert sum(a["size"] for a in capped["arms"]) == 5
    assert {a["name"] for a in capped["arms"]} == {"APP", "CORE", "EDGE"}
    with pytest.raises(DrawError, match="max_nodes"):
        atlas(max_nodes=0)


def test_scene_is_deterministic_when_store_iteration_changes():
    class ReverseStore(AtlasStore):
        def owned(self, corpus):
            return iter(reversed(list(super().owned(corpus))))

        def edges(self):
            return iter(reversed(list(super().edges())))

    cut = Cut(groups={"APP": ["pkg.app"], "CORE": ["pkg.core"]}, rest="EDGE")
    assert scene(ReverseStore(), "pkg", cut) == atlas()


def test_page_treats_source_labels_and_generation_as_data():
    sc = atlas()
    hostile = '</script><img src=x onerror="alert(1)"> `${alert(2)}` & <tag> __DATA__ __TITLE__'
    sc["title"] = hostile
    sc["nodes"][0]["label"] = hostile
    page = emit_page(sc, generation=hostile)

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    parser = Tags()
    parser.feed(page)
    assert not any(tag in {"img", "tag"} for tag, attrs in parser.tags)
    assert len([tag for tag, attrs in parser.tags if tag == "script"]) == 2
    assert next(attrs["content"] for tag, attrs in parser.tags
                if tag == "meta" and attrs.get("name") == "graphy-generation") == hostile
    data = re.search(r"const S\s*=\s*(.*?);\s*const \$", page, re.S).group(1)
    assert json.loads(data) == sc


def test_scene_requires_a_partition():
    with pytest.raises(DrawError, match="partition cut"):
        scene(AtlasStore(), "pkg", Cut())
