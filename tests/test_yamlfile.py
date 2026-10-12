"""The strict YAML reader: restricted typing, one document, no repeated keys,
no tags, no recursive aliases, UTF-8 only (settings design D-1, D-7)."""

import math

import pytest

from moskophoros.yamlfile import YamlError, load


def value(text):
    """The value `text` means as a plain scalar in a mapping."""
    return load(f"key: {text}\n".encode())["key"]


def refused(data):
    with pytest.raises(YamlError) as raised:
        load(data if isinstance(data, bytes) else data.encode("utf-8"))
    assert str(raised.value) == raised.value.problem
    return raised.value.problem


# Typing


@pytest.mark.parametrize(("text", "expected"), [("true", True), ("false", False)])
def test_booleans_are_only_true_and_false(text, expected):
    assert value(text) is expected


@pytest.mark.parametrize(
    "text", ["True", "TRUE", "False", "yes", "no", "Yes", "on", "off", "y", "n"]
)
def test_other_boolean_spellings_are_strings(text):
    assert value(text) == text


@pytest.mark.parametrize("text", ["null", "~"])
def test_null_is_only_null_and_tilde(text):
    assert value(text) is None


@pytest.mark.parametrize("text", ["Null", "NULL", "none", "None"])
def test_other_null_spellings_are_strings(text):
    assert value(text) == text


def test_an_empty_value_is_the_empty_string():
    assert load(b"default:\n") == {"default": ""}
    assert load(b"- \n- x\n") == ["", "x"]


@pytest.mark.parametrize(
    ("text", "expected"), [("0", 0), ("7", 7), ("-12", -12), ("-0", 0), ("255", 255)]
)
def test_integers_are_plain_decimal(text, expected):
    parsed = value(text)
    assert parsed == expected and type(parsed) is int


@pytest.mark.parametrize(
    "text", ["017", "00", "0x0F", "0o17", "0b11", "1:20", "+1", "1_000", "1,000"]
)
def test_other_integer_spellings_are_strings(text):
    assert value(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.5", 1.5),
        ("-2.5E-3", -0.0025),
        ("1e3", 1000.0),
        ("0.0", 0.0),
        ("2.5e+2", 250.0),
        ("-0.5", -0.5),
    ],
)
def test_floats_are_decimal_and_exponent_forms(text, expected):
    parsed = value(text)
    assert parsed == expected and type(parsed) is float


@pytest.mark.parametrize(
    "text",
    [".5", "5.", "+1.5", "01.5", "1.5_0", "1:20.5", ".inf", "-.inf", "+.inf"]
    + [".Inf", ".INF", ".nan", ".NaN", ".NAN", "inf", "nan", "NaN", "Infinity"],
)
def test_other_float_spellings_are_strings(text):
    assert value(text) == text


def test_an_overflowing_exponent_is_a_float():
    assert math.isinf(value("1e400"))


@pytest.mark.parametrize("text", ["2026-10-11", "2026-10-11T12:00:00Z", "12:30:00"])
def test_timestamps_are_strings(text):
    assert value(text) == text


@pytest.mark.parametrize(
    "text", ["'017'", '"0x0F"', "'true'", '"null"', "'1.5'", '""', "'~'"]
)
def test_quoted_values_are_strings(text):
    assert value(text) == text[1:-1]


def test_merge_and_value_keys_are_plain_strings():
    text = b"base: &b {a: 1}\nother:\n  <<: *b\n  =: 2\n"
    assert load(text) == {"base": {"a": 1}, "other": {"<<": {"a": 1}, "=": 2}}


def test_keys_are_typed_like_values():
    assert load(b"1: a\non: b\n'2': c\nnull: d\n") == {
        1: "a",
        "on": "b",
        "2": "c",
        None: "d",
    }


# Structure


def test_comments_are_allowed():
    text = b"# a library\nramps:  # named ramps\n  metal: [1, 2]  # dark to light\n"
    assert load(text) == {"ramps": {"metal": [1, 2]}}


def test_block_and_flow_forms_mean_the_same():
    assert load(b"a:\n  - 1\n  - 2\nb:\n  c: x\n") == load(b"{a: [1, 2], b: {c: x}}")


def test_anchors_and_aliases_resolve_to_ordinary_values():
    text = b"ramps:\n  metal: &metal [1, 2, 3]\n  steel: *metal\nkeep: &k {a: 1}\nalso: *k\n"
    assert load(text) == {
        "ramps": {"metal": [1, 2, 3], "steel": [1, 2, 3]},
        "keep": {"a": 1},
        "also": {"a": 1},
    }


def test_one_explicit_document_is_allowed():
    assert load(b"---\na: 1\n...\n") == {"a": 1}


def test_a_utf8_byte_order_mark_is_allowed():
    assert load("\ufeffa: 1\n".encode()) == {"a": 1}


def test_a_scalar_document():
    assert load(b"just text\n") == "just text"


# Refusals


@pytest.mark.parametrize("text", ["", "\n\n", "# only a comment\n"])
def test_an_empty_file_is_refused(text):
    assert refused(text) == "is empty: it holds no YAML document"


@pytest.mark.parametrize(
    ("text", "line"),
    [("a: 1\n---\nb: 2\n", 2), ("---\na: 1\n...\n---\nb: 2\n", 4), ("a\n---\n", 2)],
)
def test_more_than_one_document_is_refused(text, line):
    assert refused(text) == (
        f"holds more than one YAML document; the second starts at line {line}, column 1"
    )


@pytest.mark.parametrize(
    ("text", "key", "column"),
    [
        ("a: 1\nb: 2\na: 3\n", '"a"', 1),
        ("a:\n  b: 1\n  b: 2\n", '"b"', 3),
        ("a:\n  - {x: 1}\n  - {y: 1, y: 2}\n", '"y"', 12),
        ("1: a\nb: 2\n1: c\n", "1", 1),
    ],
    ids=["top-level", "nested", "in-a-list", "integer"],
)
def test_a_repeated_key_is_refused_with_its_line(text, key, column):
    assert refused(text) == f"repeats the key {key} at line 3, column {column}"


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        ("!!int 0x0F", "!!int"),
        ("!!int 017", "!!int"),
        ("!!float .nan", "!!float"),
        ("!!str 1", "!!str"),
        ("!!binary aGk=", "!!binary"),
        ("!!timestamp 2026-10-11", "!!timestamp"),
        ("!!set {a}", "!!set"),
        ("!!omap [a: 1]", "!!omap"),
        ("!!pairs [a: 1, a: 2]", "!!pairs"),
        ("!local x", "!local"),
        ("! 017", "!"),
        ("!<tag:example.com,2026:x> 1", "tag:example.com,2026:x"),
    ],
)
def test_every_tag_is_refused(text, tag):
    assert refused(f"a: 1\nkey: {text}\n") == (
        f"uses the tag {tag} at line 2, column 6; tags are not allowed"
    )


@pytest.mark.parametrize(
    ("text", "column"),
    [("&a [*a]", 5), ("&a {x: *a}", 8), ("&a [1, [2, *a]]", 12)],
    ids=["sequence", "mapping", "nested"],
)
def test_a_recursive_alias_is_refused(text, column):
    assert refused(f"x: 1\ny: {text}\n") == (
        f"the alias *a is inside its own anchor at line 2, column {column + 3}"
    )


def test_an_undefined_alias_is_refused():
    assert refused("a: *nowhere\n") == (
        "is not valid YAML at line 1, column 4: found undefined alias 'nowhere'"
    )


@pytest.mark.parametrize("text", ["? [1]\n: 2\n", "{[1]: 2}\n", "? {a: 1}\n: 2\n"])
def test_a_sequence_or_mapping_key_is_refused(text):
    assert refused(text).startswith("uses a sequence or mapping as a key at line 1")


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("{", "line 1, column 2"),
        ("a: [1, 2\n", "line 2, column 1"),
        ("a:\n\tb: 1\n", "line 2, column 1"),
        ("a: 1\n b: 2\n", "line 2, column 3"),
        ("a: 'open\n", "line 2, column 1"),
        ("%YAML 2.0\n--- a\n", "line 1, column 1"),
    ],
)
def test_malformed_yaml_is_refused_with_line_and_column(text, where):
    assert refused(text).startswith(f"is not valid YAML at {where}: ")


def test_an_unprintable_character_is_refused_with_line_and_column():
    assert refused("a: 1\nb: x\x01\n") == (
        "is not valid YAML at line 2, column 5: unacceptable character #x0001"
    )


def test_deep_nesting_is_refused():
    assert refused("[" * 100_000) == "is not valid YAML: it is nested too deeply"
    assert refused("a:\n" + "".join(" " * n + "- \n" for n in range(5000))).startswith(
        "is not valid YAML"
    )


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        (b"a: \xff\n", "is not UTF-8: invalid start byte at byte 3"),
        (
            b"\xff\xfe" + "a: 1\n".encode("utf-16-le"),
            "is not UTF-8: invalid start byte",
        ),
        (
            b"\xfe\xff" + "a: 1\n".encode("utf-16-be"),
            "is not UTF-8: invalid start byte",
        ),
        (b"a: \xc3\n", "is not UTF-8: invalid continuation byte at byte 3"),
    ],
    ids=["invalid-byte", "utf-16le-bom", "utf-16be-bom", "truncated"],
)
def test_only_utf8_is_read(data, problem):
    assert refused(data).startswith(problem)
