"""A strict reader for the YAML files the owner writes (settings design D-1,
D-7).

It is PyYAML's safe loader with less implicit typing, so a value means only
what it looks like:

- booleans are exactly `true` and `false`;
- null is exactly `null` and `~`, and an empty value is the empty string;
- integers are exactly plain decimal, `-?(0|[1-9][0-9]*)`;
- floats are JSON's numbers with a fraction, an exponent or both;
- everything else, timestamps, `<<` and `=` included, is a string.

A file holds exactly one document, repeats no key at any level, and uses no
explicit tag and no alias inside its own anchor. Input is UTF-8 only.
"""

import json
import re

import yaml
from yaml.events import AliasEvent, StreamEndEvent

_YAML_TAG = "tag:yaml.org,2002:"


class YamlError(ValueError):
    """Bad YAML input. `problem` reads after the file's name."""

    def __init__(self, problem):
        self.problem = problem
        super().__init__(problem)


def load(data):
    """The one document in the UTF-8 YAML bytes `data`, as plain Python values:
    dicts, lists, strings, integers, floats, booleans and `None`.

    Raises `YamlError` for bad input.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise YamlError(f"is not UTF-8: {error.reason} at byte {error.start}") from None
    loader = None
    try:
        loader = _Loader(text)
        loader.get_event()  # The stream start.
        if loader.check_event(StreamEndEvent):
            raise YamlError("is empty: it holds no YAML document")
        node = loader.compose_document()
        if not loader.check_event(StreamEndEvent):
            second = loader.get_event()
            raise YamlError(
                "holds more than one YAML document; the second starts at "
                + _where(second.start_mark)
            )
        return loader.construct_document(node)
    except YamlError:
        raise
    except _Refused as error:
        raise YamlError(
            f"{error.problem} at {_where(error.mark)}{error.reason}"
        ) from None
    except yaml.MarkedYAMLError as error:
        raise YamlError(_invalid(error)) from None
    except yaml.reader.ReaderError as error:
        line = text.count("\n", 0, error.position) + 1
        column = error.position - (text.rfind("\n", 0, error.position) + 1) + 1
        raise YamlError(
            f"is not valid YAML at line {line}, column {column}: unacceptable "
            f"character #x{error.character:04x}"
        ) from None
    except RecursionError:
        raise YamlError(
            f"is not valid YAML{_at(loader)}: it is nested too deeply"
        ) from None
    except (ValueError, OverflowError) as error:
        # PyYAML's scanner converts some tokens with Python built-ins that
        # raise plain errors, such as an escape beyond U+10FFFF (`chr`) or a
        # `%YAML` version longer than `int`'s digit limit.
        raise YamlError(
            f"is not valid YAML{_at(loader)}: cannot read a token ({error})"
        ) from None
    finally:
        if loader is not None:
            loader.dispose()


class _Refused(Exception):
    def __init__(self, problem, mark, reason=""):
        self.problem = problem
        self.mark = mark
        self.reason = reason


class _Loader(yaml.SafeLoader):
    # Only the resolvers registered below; none of PyYAML's YAML 1.1 ones.
    yaml_implicit_resolvers = {}

    def __init__(self, stream):
        super().__init__(stream)
        self._open_anchors = []

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, AliasEvent):
            if event.anchor in self._open_anchors:
                raise _Refused(
                    f"the alias *{event.anchor} is inside its own anchor",
                    event.start_mark,
                )
            return super().compose_node(parent, index)
        if event.tag is not None:
            raise _Refused(
                f"uses the tag {_tag(event.tag)}",
                event.start_mark,
                "; tags are not allowed",
            )
        if event.anchor is None:
            return super().compose_node(parent, index)
        self._open_anchors.append(event.anchor)
        try:
            return super().compose_node(parent, index)
        finally:
            self._open_anchors.pop()

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                repeated = key in mapping
            except TypeError:
                raise _Refused(
                    "uses a sequence or mapping as a key", key_node.start_mark
                ) from None
            if repeated:
                raise _Refused(f"repeats the key {_shown(key)}", key_node.start_mark)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _resolve(tag, pattern, first):
    _Loader.add_implicit_resolver(_YAML_TAG + tag, re.compile(pattern), list(first))


_DIGITS = "-0123456789"
_resolve("bool", r"(?:true|false)\Z", "tf")
_resolve("null", r"(?:null|~)\Z", "n~")
_resolve("int", r"-?(?:0|[1-9][0-9]*)\Z", _DIGITS)
_resolve(
    "float",
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][-+]?[0-9]+)?|[eE][-+]?[0-9]+)\Z",
    _DIGITS,
)


def _integer(_, node):
    try:
        return int(node.value)
    except ValueError:
        # Python refuses to convert very long decimal strings.
        raise _Refused(
            f"has an integer of {len(node.value.lstrip('-'))} digits, too long to read",
            node.start_mark,
        ) from None


_Loader.add_constructor(_YAML_TAG + "int", _integer)
_Loader.add_constructor(_YAML_TAG + "float", lambda _, node: float(node.value))


def _where(mark):
    # PyYAML's marks count from 0; people count lines and columns from 1.
    return f"line {mark.line + 1}, column {mark.column + 1}"


def _at(loader):
    # Where the reader stopped, for errors PyYAML gives no mark.
    return "" if loader is None else f" at {_where(loader.get_mark())}"


def _invalid(error):
    mark = error.problem_mark or error.context_mark
    problem = error.problem or error.context
    message = "is not valid YAML"
    if mark is not None:
        message += f" at {_where(mark)}"
    message += f": {problem}"
    if error.problem and error.context:
        message += f" ({error.context}"
        if error.context_mark is not None:
            message += f" at {_where(error.context_mark)}"
        message += ")"
    return message


def _tag(tag):
    if tag.startswith(_YAML_TAG):
        return "!!" + tag[len(_YAML_TAG) :]
    return tag


def _shown(key):
    try:
        return json.dumps(key, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return repr(key)
