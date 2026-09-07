"""The per-file receipt a producer writes beside its records, and the splice that reads it.

A producer emits records file by file; a node dict keyed by id keeps the position of an id's first
emission and (``"last"`` semantics, python_ast) the value of its last, or (``"first"`` semantics,
typescript_ast) the first. When no id crosses files, each file's node records are a contiguous
span of the dict and its edges a contiguous span of the list, so a re-mint takes an untouched
file's records straight off the previous nodes.json and edges.json. When an id does cross files
the receipt stores exactly the records the span cannot recover — the later file's own record
(``extra``, with the position it was emitted at) and, under ``"last"``, the first file's own record
that a later file overwrote (``own``, by slot) — so the replay is the full mint's replay record for
record, and the shard written is byte-identical. Nothing else is stored: an id a file emits twice
is one slot, and the span already carries its position and its winning value."""
from __future__ import annotations

from typing import Any

__all__ = ["Receipt", "splice"]


class Receipt:
    def __init__(self, semantics: str):
        assert semantics in ("first", "last")
        self.semantics = semantics
        self.first_by: dict[str, str] = {}        # id -> the file that inserted it
        self.last_by: dict[str, str] = {}         # id -> the file whose record sits in the dict
        self.emitted: dict[str, list[dict]] = {}  # file -> its node records, in emission order
        self.files: dict[str, dict] = {}          # file -> {sha256, nodes, edges}
        self.cross = 0
        self.parsed = 0

    def file(self, rel: str, sha: str, n_recs: list[dict], e_recs: list[dict], nodes: dict, *, parsed: bool) -> None:
        """Insert one file's records under the producer's semantics and account for them."""
        slots = 0
        for rec in n_recs:
            i = rec["id"]
            owner = self.first_by.setdefault(i, rel)
            if owner == rel:
                if i not in nodes:
                    slots += 1
            else:
                self.cross += 1
            if self.semantics == "last":
                nodes[i] = rec
                self.last_by[i] = rel
            elif i not in nodes:
                nodes[i] = rec
                self.last_by[i] = rel
        self.emitted[rel] = n_recs
        self.files[rel] = {"sha256": sha, "nodes": slots, "edges": len(e_recs)}
        self.parsed += 1 if parsed else 0

    def finish(self, pin: str) -> dict:
        """The receipt: every file's span, and the records a span cannot recover."""
        for rel, recs in self.emitted.items():
            extra: list = []
            own: dict[str, dict] = {}
            seen_here: dict[str, int] = {}           # id -> index of this file's first emission among its slots
            slot = 0
            for rec in recs:
                i = rec["id"]
                mine = self.first_by[i] == rel
                if mine:
                    if i not in seen_here:
                        seen_here[i] = slot
                        slot += 1
                        if self.last_by[i] != rel:           # overwritten by a later file: keep this file's own
                            own[str(seen_here[i])] = rec
                    elif self.last_by[i] != rel and self.semantics == "last":
                        own[str(seen_here[i])] = rec         # its last emission is the one that would have won
                else:
                    if i not in seen_here:
                        seen_here[i] = slot
                        extra.append([slot, rec])
                    elif self.semantics == "last":
                        extra[[x[1]["id"] for x in extra].index(i)][1] = rec
            if extra:
                self.files[rel]["extra"] = extra
            if own:
                self.files[rel]["own"] = own
        return {"pin": pin, "spliceable": True, "cross_file": self.cross, "parsed": self.parsed,
                "reused": len(self.files) - self.parsed, "files": self.files}


def splice(span_nodes: list[dict], span_edges: list[dict], f: dict) -> tuple[list[dict], list[dict]]:
    """A file's records, replayed from its span and the receipt's stored records."""
    recs = list(span_nodes)
    for slot, rec in (f.get("own") or {}).items():
        recs[int(slot)] = rec
    for at, rec in sorted(f.get("extra") or [], key=lambda x: x[0], reverse=True):
        recs.insert(int(at), rec)
    return recs, span_edges
