"""lightning — ripgrep discovers, an AST walk-out anchors every hit to its enclosing block.

Doors: a bare term (where is X) · --containers (who reads X) · --cooccur A --with B ·
--stats · --files-from (the pipe). The two memory doors are their own binaries:
`graphy.lightning.bloodhound` and `graphy.lightning.reseed_graph`.
"""
from .blitz_hunt import Lightning
from .block_blast import find_blocks, find_blocks_regex, find_containing_block, find_python_blocks
from .context_strike import expand_and_merge, find_code_boundary, find_matches
from .models import CodeBlock, CodeChunk, CodeMatch, FileHit, LightningResult
from .pattern_splinter import (
    build_code_pattern, detokenize, get_identifier_variations, split_identifier, token_count, tokenize,
)

__all__ = [
    "Lightning", "LightningResult", "CodeBlock", "CodeMatch", "CodeChunk", "FileHit",
    "tokenize", "detokenize", "token_count", "split_identifier", "build_code_pattern",
    "get_identifier_variations", "find_python_blocks", "find_blocks_regex", "find_blocks",
    "find_containing_block", "find_code_boundary", "find_matches", "expand_and_merge",
]
