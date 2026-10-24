"""The output path template grammar (export design P-7, part 3)."""

import pytest

from moskophoros import templates
from moskophoros.templates import (
    ATLAS_PATH,
    FRAME_PATH,
    SHEET_PATH,
    Field,
    TemplateError,
    expand,
    parse,
    uses,
)

ALL_VALUES = {
    "subject": "hero",
    "variant": "default",
    "clip": "walk",
    "direction": "south",
    "frame": 7,
    "map": ".normal",
}


def test_the_default_paths_are_valid_templates_of_their_formats():
    assert parse("frames/{clip}/{direction}/frame_{frame:03}{map}.png", FRAME_PATH)
    assert parse("atlases/{clip}{map}.png", ATLAS_PATH)
    assert parse("sheet{map}.png", SHEET_PATH)


def test_a_template_parses_into_literals_and_fields():
    template = parse("a/{clip}_{frame:04}{map}.png", FRAME_PATH)
    assert template.text == "a/{clip}_{frame:04}{map}.png"
    assert template.parts == (
        "a/",
        Field("clip"),
        "_",
        Field("frame", 4),
        Field("map"),
        ".png",
    )
    assert parse("{frame}", FRAME_PATH).parts == (Field("frame"),)


@pytest.mark.parametrize("width", range(1, 13))
def test_every_width_from_1_to_12_is_valid(width):
    template = parse(f"{{frame:0{width}}}", FRAME_PATH)
    assert template.parts == (Field("frame", width),)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("{frame}", "7"),
        ("{frame:01}", "7"),
        ("{frame:03}", "007"),
        ("{frame:010}", "0000000007"),
        ("{frame:012}", "000000000007"),
        ("{frame:02}", "07"),
    ],
)
def test_frame_widths_pad_and_never_truncate(text, expected):
    assert expand(parse(text, FRAME_PATH), ALL_VALUES) == expected
    assert expand(parse("{frame:03}", FRAME_PATH), {"frame": 1234}) == "1234"
    assert expand(parse("{frame:01}", FRAME_PATH), {"frame": 123}) == "123"


def test_each_token_expands_to_its_value():
    template = parse(
        "{subject}/{variant}/{clip}/{direction}/{frame:02}{map}.png", FRAME_PATH
    )
    assert expand(template, ALL_VALUES) == "hero/default/walk/south/07.normal.png"
    assert (
        expand(template, ALL_VALUES | {"map": ""}) == "hero/default/walk/south/07.png"
    )


def test_the_literals_are_ascii_letters_digits_dot_underscore_slash_and_dash():
    text = "Aa09._/-x.png"
    assert expand(parse(text, SHEET_PATH), {}) == text


@pytest.mark.parametrize(
    ("kind", "allowed"),
    [
        (FRAME_PATH, {"subject", "variant", "clip", "direction", "frame", "map"}),
        (ATLAS_PATH, {"subject", "variant", "clip", "map"}),
        (SHEET_PATH, {"subject", "variant", "map"}),
    ],
)
def test_each_format_allows_exactly_its_tokens(kind, allowed):
    for token in templates.TOKENS:
        text = f"{{{token}}}.png"
        if token in allowed:
            assert uses(parse(text, kind), token)
        else:
            with pytest.raises(TemplateError, match="cannot use"):
                parse(text, kind)
    if "frame" not in allowed:
        with pytest.raises(TemplateError, match="cannot use"):
            parse("{frame:03}.png", kind)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("", "is empty"),
        ("{", "unmatched '{'"),
        ("a{clip", "unmatched '{'"),
        ("a}", "unmatched '}'"),
        ("}{clip}", "unmatched '}'"),
        ("{clip{frame}}", "unmatched '{'"),
        ("{{clip}}", "brace escapes are not supported"),
        ("a{{b", "brace escapes are not supported"),
        ("{}", "unknown token '{}'"),
        ("{bogus}", "unknown token '{bogus}'"),
        ("{Clip}", "unknown token '{Clip}'"),
        ("{frame:3}", "takes no formatting"),
        ("{frame:00}", "takes no formatting"),
        ("{frame:0}", "takes no formatting"),
        ("{frame:0012}", "takes no formatting"),
        ("{frame:003}", "takes no formatting"),
        ("{frame:d}", "takes no formatting"),
        ("{frame:03d}", "takes no formatting"),
        ("{frame:013}", "the minimum width is at most 12"),
        ("{frame:099}", "the minimum width is at most 12"),
        ("{clip:03}", "takes no formatting"),
        ("{clip!r}", "unknown token"),
        ("{ clip }", "takes no formatting"),
        ("{clip.name}", "unknown token"),
        ("{clip[0]}", "unknown token"),
        ("$HOME/{clip}", "the character '$'"),
        ("~/{clip}", "the character '~'"),
        ("*/{clip}", "the character '*'"),
        ("{clip} x", "the character ' '"),
        ("a\\b", "the character '\\\\'"),
        ("é{clip}", "the character 'é'"),
        ("{clip}é", "the character 'é'"),
        ("{clip}\n", "the character '\\n'"),
        ("{clip}\x00", "the character '\\x00'"),
        ("%s{clip}", "the character '%'"),
    ],
)
def test_a_bad_template_is_refused_with_the_reason(text, problem):
    with pytest.raises(TemplateError) as raised:
        parse(text, FRAME_PATH)
    assert problem in str(raised.value)


def test_a_template_must_be_a_string():
    for value in (None, 3, ["a"], b"a.png"):
        with pytest.raises(TemplateError, match="is not a string"):
            parse(value, FRAME_PATH)


def test_a_kind_must_be_known():
    with pytest.raises(ValueError, match="not a template kind"):
        parse("x", "other")
