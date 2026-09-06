
import bisect
import re

from .models import CodeBlock, CodeMatch, CodeChunk
from .pattern_splinter import tokenize, detokenize
from .block_blast import find_containing_block


def find_code_boundary(
    text: str,
    match_char_pos: int,
    direction: str,
    blocks: list[CodeBlock],
    min_tokens: int = 30,
    max_tokens: int = 300,
) -> int:
    tokens = tokenize(text)
    total_tokens = len(tokens)

    char_to_token = []
    current_char = 0
    for i, token in enumerate(tokens):
        for _ in token:
            char_to_token.append(i)
            current_char += 1

    if match_char_pos >= len(char_to_token):
        match_token = len(tokens) - 1
    else:
        match_token = char_to_token[match_char_pos]

    block = find_containing_block(match_char_pos, blocks)

    if block:
        if direction == "forward":
            if block.end_char < len(char_to_token):
                return min(char_to_token[block.end_char - 1], match_token + max_tokens)
            return min(total_tokens, match_token + max_tokens)
        else:
            if block.start_char < len(char_to_token):
                return max(char_to_token[block.start_char], match_token - max_tokens)
            return max(0, match_token - max_tokens)

    lines = text.split("\n")
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)

    current_line = 0
    for i, start in enumerate(line_starts):
        if start > match_char_pos:
            current_line = i - 1
            break

    if direction == "forward":
        for i in range(current_line + 1, min(current_line + 50, len(lines))):
            line = lines[i] if i < len(lines) else ""
            if not line.strip() or re.match(r"^(class|def|async\s+def)\s", line):
                target_char = line_starts[i] if i < len(line_starts) else len(text)
                if target_char < len(char_to_token):
                    return min(char_to_token[target_char], match_token + max_tokens)
        return min(total_tokens, match_token + max_tokens)
    else:
        for i in range(current_line - 1, max(current_line - 50, -1), -1):
            if i < 0:
                break
            line = lines[i]
            if not line.strip() or re.match(r"^(class|def|async\s+def)\s", line):
                target_char = line_starts[i + 1] if i + 1 < len(line_starts) else 0
                if target_char < len(char_to_token):
                    return max(char_to_token[target_char], match_token - max_tokens)
        return max(0, match_token - max_tokens)


def find_matches(text: str, pattern: re.Pattern, blocks: list[CodeBlock]) -> list[CodeMatch]:
    tokens = tokenize(text)
    matches = []

    token_starts = []
    pos = 0
    for token in tokens:
        token_starts.append(pos)
        pos += len(token)
    total_token_chars = pos

    line_starts = [0]
    for line in text.split("\n"):
        line_starts.append(line_starts[-1] + len(line) + 1)

    def _tok_at(c: int) -> int:
        if c >= total_token_chars:
            return len(tokens) - 1
        return bisect.bisect_right(token_starts, c) - 1

    sorted_blocks = sorted(blocks, key=lambda b: b.start_char)
    next_block = 0
    active: list[CodeBlock] = []

    def _containing(c: int) -> CodeBlock | None:
        nonlocal next_block, active
        while next_block < len(sorted_blocks) and sorted_blocks[next_block].start_char <= c:
            active.append(sorted_blocks[next_block])
            next_block += 1
        if any(b.end_char <= c for b in active):
            active = [b for b in active if b.end_char > c]
        named = nameless = None
        for b in active:
            if b.name is None:
                if nameless is None or (b.end_char - b.start_char) < (nameless.end_char - nameless.start_char):
                    nameless = b
            elif named is None or (b.end_char - b.start_char) < (named.end_char - named.start_char):
                named = b
        return named or nameless

    for match in pattern.finditer(text):
        char_start = match.start()
        char_end = match.end()

        start_token = _tok_at(char_start)
        end_token = _tok_at(char_end - 1)

        line_num = bisect.bisect_right(line_starts, char_start)

        block = _containing(char_start)
        block_name = f"{block.block_type}:{block.name}" if block and block.name else None

        matches.append(
            CodeMatch(
                start_char=char_start,
                end_char=char_end,
                start_token=start_token,
                end_token=end_token,
                matched_text=match.group(),
                line_number=line_num,
                containing_block=block_name,
            )
        )

    return matches


def expand_and_merge(
    text: str,
    matches: list[CodeMatch],
    blocks: list[CodeBlock],
    token_radius: int = 100,
    merge_gap: int = 50,
    smart_expand: bool = True,
    context_lines: int = 10,
) -> list[CodeChunk]:
    if not matches:
        return []

    tokens = tokenize(text)
    total_tokens = len(tokens)

    lines = text.split("\n")
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)

    token_char = [0]
    for token in tokens:
        token_char.append(token_char[-1] + len(token))

    def token_to_line(token_idx: int) -> int:
        char_pos = token_char[min(token_idx, len(tokens))]
        return min(bisect.bisect_right(line_starts, char_pos), len(lines))

    def line_to_token(line_num: int) -> int:
        if line_num <= 0:
            return 0
        if line_num >= len(line_starts):
            return total_tokens
        char_pos = line_starts[line_num - 1]
        return min(bisect.bisect_left(token_char, char_pos), total_tokens)

    expanded_spans = []
    for match in matches:
        if smart_expand:
            block = find_containing_block(match.start_char, blocks)
            if block:
                block_start_line = max(1, text[: block.start_char].count("\n") + 1)
                block_end_line = max(1, text[: block.end_char].count("\n") + 1)
                match_line = match.line_number

                start_line = max(block_start_line, match_line - context_lines)
                end_line = min(block_end_line, match_line + context_lines)

                start = line_to_token(start_line)
                end = line_to_token(end_line)
            else:
                start_line = max(1, match.line_number - context_lines)
                end_line = match.line_number + context_lines
                start = line_to_token(start_line)
                end = line_to_token(end_line)
        else:
            start = max(0, match.start_token - token_radius)
            end = min(total_tokens, match.end_token + token_radius)

        included_blocks = []
        containing = find_containing_block(match.start_char, blocks)
        anchor: tuple[int, int] | None = None
        if containing and containing.name:
            included_blocks.append(f"{containing.block_type}:{containing.name}")
            c_start_line = max(1, text[: containing.start_char].count("\n") + 1)
            anchor = (c_start_line, min(c_start_line + 1, len(lines)))
        span_start_char = token_char[min(start, len(tokens))]
        span_end_char = token_char[min(end, len(tokens))]
        for block in blocks:
            if block.name and block.start_char >= span_start_char:
                if block.end_char <= span_end_char:
                    label = f"{block.block_type}:{block.name}"
                    if label not in included_blocks:
                        included_blocks.append(label)

        expanded_spans.append((start, end, 1, included_blocks, anchor))

    expanded_spans.sort(key=lambda x: x[0])

    merged = []
    current_start, current_end, current_count, current_blocks, current_anchor = expanded_spans[0]

    for start, end, count, blocks_list, anchor in expanded_spans[1:]:
        gap = start - current_end

        if gap <= merge_gap:
            current_end = max(current_end, end)
            current_count += count
            current_blocks = list(set(current_blocks + blocks_list))
            current_anchor = current_anchor or anchor
        else:
            merged.append((current_start, current_end, current_count, current_blocks, current_anchor))
            current_start, current_end, current_count, current_blocks, current_anchor = (
                start, end, count, blocks_list, anchor,
            )

    merged.append((current_start, current_end, current_count, current_blocks, current_anchor))

    chunks = []
    for start, end, count, blocks_list, anchor in merged:
        chunk_tokens = tokens[start:end]
        chunk_text = detokenize(chunk_tokens).strip()
        chunk_start_line = token_to_line(start)

        anchor_head: list = []
        if anchor and chunk_start_line > anchor[0] + 1:
            for ln in range(anchor[0], anchor[1] + 1):
                if 1 <= ln <= len(lines):
                    anchor_head.append([ln, lines[ln - 1]])

        chunks.append(
            CodeChunk(
                start_token=start,
                end_token=end,
                start_line=chunk_start_line,
                end_line=token_to_line(end),
                text=chunk_text,
                match_count=count,
                is_merged=(count > 1),
                blocks_included=blocks_list,
                anchor_head=anchor_head,
            )
        )

    return chunks
