"""Output path templates: the grammar, its checks and expansion (export
design P-7, part 3).

A template is a relative path written with a few tokens in braces:

    template = (literal | "{" token "}" | "{frame:0" width "}")+
    token    = "subject" | "variant" | "clip" | "direction" | "frame" | "map"
    width    = "1" | "2" | ... | "12"
    literal  = one character from [A-Za-z0-9._/-]

There are no brace escapes and no other formatting, access or expansion.
Which tokens a template may use depends on what it names: a frame file, a
clip atlas or the combined sheet. This module checks syntax and expands a
parsed template; whether the expanded paths are acceptable and distinct is
`outputs`' business. Everything here is pure.
"""

import re
from dataclasses import dataclass

SUBJECT = "subject"
VARIANT = "variant"
CLIP = "clip"
DIRECTION = "direction"
FRAME = "frame"
MAP = "map"
TOKENS = (SUBJECT, VARIANT, CLIP, DIRECTION, FRAME, MAP)
# The widest `{frame:0N}` minimum width.
MAX_WIDTH = 12

# What a template names, and the tokens each may use.
FRAME_PATH = "frame_path"
ATLAS_PATH = "atlas_path"
SHEET_PATH = "sheet_path"
ALLOWED = {
    FRAME_PATH: frozenset(TOKENS),
    ATLAS_PATH: frozenset(TOKENS) - {DIRECTION, FRAME},
    SHEET_PATH: frozenset(TOKENS) - {CLIP, DIRECTION, FRAME},
}
_NOUN = {
    FRAME_PATH: "a frame path",
    ATLAS_PATH: "an atlas path",
    SHEET_PATH: "a sheet path",
}

_LITERAL = re.compile(r"[A-Za-z0-9._/-]", re.ASCII)
_WIDTH = re.compile(r"frame:0([1-9][0-9]?)", re.ASCII)


class TemplateError(ValueError):
    """A template the grammar or its format's token list refuses; the message
    reads after `the template`, such as `is empty`."""


@dataclass(frozen=True)
class Field:
    """A token in a parsed template; `width` is `{frame:0N}`'s minimum width,
    else None."""

    token: str
    width: int | None = None


@dataclass(frozen=True)
class Template:
    """A parsed template: its text, and its parts in order, each a literal
    string or a `Field`."""

    text: str
    kind: str
    parts: tuple


def parse(text, kind):
    """The template `text` names by `kind` (`FRAME_PATH`, `ATLAS_PATH` or
    `SHEET_PATH`), or `TemplateError` saying what is wrong with it."""
    if kind not in ALLOWED:
        raise ValueError(f"not a template kind: {kind!r}")
    if not isinstance(text, str):
        raise TemplateError(f"is not a string, but {text!r}")
    if not text:
        raise TemplateError("is empty")
    parts = []
    literal = []
    position = 0
    while position < len(text):
        char = text[position]
        if char == "}":
            raise TemplateError(f"has an unmatched '}}' at character {position + 1}")
        if char != "{":
            if not _LITERAL.fullmatch(char):
                raise TemplateError(
                    f"has the character {char!r} at character {position + 1}; "
                    "literals are limited to A-Z a-z 0-9 . _ / and -"
                )
            literal.append(char)
            position += 1
            continue
        end = position + 1
        while end < len(text) and text[end] not in "{}":
            end += 1
        if end == len(text) or text[end] == "{":
            if text.startswith("{{", position):
                raise TemplateError(
                    f"has '{{{{' at character {position + 1}; brace escapes are "
                    "not supported"
                )
            raise TemplateError(f"has an unmatched '{{' at character {position + 1}")
        content = text[position + 1 : end]
        field = _field(content, kind)
        if literal:
            parts.append("".join(literal))
            literal = []
        parts.append(field)
        position = end + 1
    if literal:
        parts.append("".join(literal))
    return Template(text, kind, tuple(parts))


def _field(content, kind):
    width = None
    token = content
    matched = _WIDTH.fullmatch(content)
    if matched:
        token, width = FRAME, int(matched.group(1))
        if width > MAX_WIDTH:
            raise TemplateError(
                f"has '{{{content}}}': the minimum width is at most {MAX_WIDTH}"
            )
    elif token == FRAME:
        pass
    elif token not in TOKENS:
        if ":" in content or " " in content:
            raise TemplateError(
                f"has '{{{content}}}': a token takes no formatting except "
                "'{frame:0N}' with N from 1 to 12"
            )
        raise TemplateError(
            f"has the unknown token '{{{content}}}'; the tokens are "
            + ", ".join(f"{{{name}}}" for name in TOKENS)
        )
    if token not in ALLOWED[kind]:
        raise TemplateError(f"uses '{{{token}}}', which {_NOUN[kind]} cannot use")
    return Field(token, width)


def expand(template, values):
    """The path `template` gives, with each token replaced by its entry in
    `values` (a mapping from token name to a string, or for `frame` an
    integer). A token the template uses must be in `values`; the others are
    ignored."""
    pieces = []
    for part in template.parts:
        if isinstance(part, str):
            pieces.append(part)
        elif part.token == FRAME:
            index = values[FRAME]
            pieces.append(
                str(index) if part.width is None else f"{index:0{part.width}d}"
            )
        else:
            pieces.append(values[part.token])
    return "".join(pieces)


def uses(template, token):
    """Whether `template` has the token `token`."""
    return any(
        isinstance(part, Field) and part.token == token for part in template.parts
    )
