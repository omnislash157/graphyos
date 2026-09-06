
from __future__ import annotations


def neutralize(text: str) -> str:
    n = len(text)
    out: list[str] = []
    in_squote = in_dquote = in_line_comment = in_block_comment = False
    template_stack: list[int] = []
    last_sig = ""
    _DIV_PRECEDERS = set("})]")
    i = 0
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        in_template_text = bool(template_stack) and template_stack[-1] == 0
        if in_line_comment:
            if c == "\n":
                in_line_comment = False; out.append(c)
            else:
                out.append(" ")
            i += 1; continue
        if in_block_comment:
            if c == "*" and nxt == "/":
                in_block_comment = False; out.append("  "); i += 2
            else:
                out.append("\n" if c == "\n" else " "); i += 1
            continue
        if in_squote:
            if c == "\\":
                out.append("  "); i += 2; continue
            if c == "'":
                in_squote = False; out.append(" "); i += 1; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        if in_dquote:
            if c == "\\":
                out.append("  "); i += 2; continue
            if c == '"':
                in_dquote = False; out.append(" "); i += 1; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        if in_template_text:
            if c == "\\":
                out.append("  "); i += 2; continue
            if c == "`":
                template_stack.pop(); out.append(" "); i += 1; continue
            if c == "$" and nxt == "{":
                template_stack[-1] = 1; out.append("${"); i += 2; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        if c == "/" and nxt == "/":
            in_line_comment = True; out.append("  "); i += 2; continue
        if c == "/" and nxt == "*":
            in_block_comment = True; out.append("  "); i += 2; continue
        if c == "/" and not (last_sig.isalnum() or last_sig in ")]}_$."):
            out.append(" "); i += 1
            in_class = False
            while i < n:
                rc = text[i]
                if rc == "\\":
                    out.append("  "); i += 2; continue
                if rc == "\n":
                    out.append("\n"); i += 1; continue
                if rc == "[":
                    in_class = True
                elif rc == "]":
                    in_class = False
                elif rc == "/" and not in_class:
                    out.append(" "); i += 1; break
                out.append(" "); i += 1
            last_sig = "/"
            continue
        if c == "'":
            in_squote = True; out.append(" "); i += 1; continue
        if c == '"':
            in_dquote = True; out.append(" "); i += 1; continue
        if c == "`":
            template_stack.append(0); out.append(" "); i += 1; continue
        if c == "{":
            if template_stack and template_stack[-1] > 0:
                template_stack[-1] += 1
            out.append(c); last_sig = c; i += 1; continue
        if c == "}":
            if template_stack and template_stack[-1] > 0:
                template_stack[-1] -= 1
            out.append(c); last_sig = c; i += 1; continue
        out.append(c)
        if not c.isspace():
            last_sig = c
        i += 1
    return "".join(out)


def brace_block(text: str, open_brace_pos: int) -> tuple[str, int]:
    n = len(text)
    out: list[str] = []
    depth = 0
    i = open_brace_pos
    in_squote = False
    in_dquote = False
    in_line_comment = False
    in_block_comment = False
    template_stack: list[int] = []

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        in_template = bool(template_stack)
        in_template_text = in_template and template_stack[-1] == 0

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
                out.append(c)
            else:
                out.append(" ")
            i += 1
            continue
        if in_block_comment:
            if c == "*" and nxt == "/":
                in_block_comment = False
                out.append("  ")
                i += 2
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
            continue

        if in_squote:
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == "'":
                in_squote = False
                out.append(" ")
                i += 1
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
            continue
        if in_dquote:
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == '"':
                in_dquote = False
                out.append(" ")
                i += 1
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
            continue

        if in_template_text:
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == "`":
                template_stack.pop()
                out.append(" ")
                i += 1
                continue
            if c == "$" and nxt == "{":
                template_stack[-1] = 1
                out.append("${")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
            continue

        if c == "/" and nxt == "/":
            in_line_comment = True
            out.append("  ")
            i += 2
            continue
        if c == "/" and nxt == "*":
            in_block_comment = True
            out.append("  ")
            i += 2
            continue
        if c == "'":
            in_squote = True
            out.append(" ")
            i += 1
            continue
        if c == '"':
            in_dquote = True
            out.append(" ")
            i += 1
            continue
        if c == "`":
            template_stack.append(0)
            out.append(" ")
            i += 1
            continue

        if c == "{":
            if in_template and template_stack[-1] > 0:
                template_stack[-1] += 1
            else:
                depth += 1
            out.append(c)
            i += 1
            continue
        if c == "}":
            if in_template and template_stack[-1] > 0:
                template_stack[-1] -= 1
                out.append(c)
                i += 1
                continue
            depth -= 1
            out.append(c)
            i += 1
            if depth == 0:
                close_pos = i - 1
                return "".join(out[1:-1]), close_pos
            continue

        out.append(c)
        i += 1

    return "".join(out[1:]) if out else "", n
