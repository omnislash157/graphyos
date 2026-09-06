
import re


def tokenize(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text)


def detokenize(tokens: list[str]) -> str:
    return "".join(tokens)


def token_count(text: str) -> int:
    return len([t for t in tokenize(text) if t.strip()])


def split_identifier(name: str) -> list[str]:
    parts = re.split(r"[-_.\s]+", name)

    result = []
    for part in parts:
        if not part:
            continue
        camel_parts = re.findall(
            r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", part
        )
        if camel_parts:
            result.extend(camel_parts)
        else:
            result.append(part)

    return [p for p in result if p]


def build_code_pattern(term: str, case_insensitive: bool = True, loose: bool = False) -> re.Pattern:
    parts = split_identifier(term)

    if not parts:
        flags = re.IGNORECASE if case_insensitive else 0
        return re.compile(re.escape(term), flags)

    separator = r"[-_./\\\s]?"
    if loose and len(parts) == 1:
        chars = [re.escape(c) for c in parts[0]]
        pattern = separator.join(chars)
    else:
        escaped_parts = [re.escape(p) for p in parts]
        pattern = separator.join(escaped_parts)

    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(pattern, flags)


def get_identifier_variations(term: str) -> list[str]:
    parts = split_identifier(term)

    if not parts:
        return [term]

    lower_parts = [p.lower() for p in parts]

    return [
        "".join(lower_parts),
        "_".join(lower_parts),
        "-".join(lower_parts),
        ".".join(lower_parts),
        "".join(p.capitalize() for p in lower_parts),
        lower_parts[0] + "".join(p.capitalize() for p in lower_parts[1:]),
        "_".join(p.upper() for p in lower_parts),
    ]
