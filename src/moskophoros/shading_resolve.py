"""Resolve the shading response of every material from the global settings
and a material library (shading design contract 2, D-10, D-33, D-39).

Each response leaf takes its value from the material's entry, else the
library's own shade, else the resolved global setting; the global setting is
whichever layer won, so an explicit global option cannot defeat a library or
material value. The shade range takes the same route, and an entry's capture
values fall back to the global ones. The cross-field rules, the strengths'
unit budget and the brightness order, are checked on these resolved values
only, for the global response, then the library's, then every entry,
unused ones included, and each failure names every contributing value and
where it came from.

This is internal until SHD-6 wires it to the command: nothing here is
reachable from a public option, file or sheet record. It is pure.
"""

from dataclasses import dataclass
from types import MappingProxyType

from moskophoros import settings, shading


@dataclass(frozen=True)
class Look:
    """What one identity class resolves to: its response, the shade range it
    spans and the capture values its material is captured with. The ramp it
    takes is the library's business (`stylize`), not part of the look."""

    response: shading.Response
    shade_range: tuple[int, int]
    ao_distance_m: float
    occlusion_weight: float
    convexity_weight: float


@dataclass(frozen=True)
class Resolved:
    """The resolved shading: the global `settings`, the `base` look of the
    global values, the `fallback` look of the parts the library gives nothing
    of their own, which is a material with no entry and a part with no
    identity (the `base` without a library), and the look of each entry in
    `materials` by name."""

    settings: shading.Settings
    base: Look
    fallback: Look
    materials: MappingProxyType

    def look(self, name):
        """The look of the material `name`, or of a part with no identity
        when `name` is None; one the library has no entry for takes the
        fallback."""
        return self.materials.get(name, self.fallback)


def resolve(values, library=None, *, has_palette, origins=None):
    """The `Resolved` shading for the global settings `values`, a mapping of
    the settings' names, such as `shade.key.strength`, to checked values,
    with a leaf it leaves out at its default, and the `library`, a
    `materials.Library`, or None for none.

    `origins` maps a setting's name to where its value came from, such as
    `--brightness-ceiling` or `config.yaml line 12, column 3` (see
    `settings.origins`); a setting it leaves out is shown as the shipped
    default. `has_palette` is whether a palette is in force: a library needs
    one, and so does a snap target other than `off`, whatever the mode.

    Raises `shading.ShadingError` with every problem, in a fixed order: the
    palette rules, the global response, the library's, then the entries by
    name. A rule a library or an entry could only repeat from the level
    above, because it gives none of the values the rule reads, is reported
    once, at the level that set them.
    """
    origins = origins or {}
    given = shading.settings_of(values)
    problems = []
    if library is not None and not has_palette:
        problems.append("the material library needs a palette")
    if given.snap != "off" and not has_palette:
        snap_origin = origins.get("shade.snap", shading.DEFAULT_ORIGIN)
        problems.append(
            f"shade.snap {shading.quote(given.snap)} ({snap_origin}) needs a "
            "palette, even when the mode leaves snap unused"
        )
    global_ = {
        path: shading.Sourced(
            getattr(given.response, field),
            origins.get(f"shade.{path}", shading.DEFAULT_ORIGIN),
        )
        for path, field in shading.FIELDS.items()
    }
    problems += _problems(global_, None, "")
    global_range = values.get("shade.range", settings.DEFAULTS["shade.range"])
    capture = {
        name: values.get(f"shade.{name}", settings.DEFAULTS[f"shade.{name}"])
        for name in ("ao_distance_m", "occlusion_weight", "convexity_weight")
    }
    base = _look(global_, global_range, capture)
    if library is None:
        if problems:
            raise shading.ShadingError(problems)
        return Resolved(given, base, base, MappingProxyType({}))
    level = _overlay(global_, library.shade, library, ("shade",))
    fallback_range = (
        global_range
        if library.shade is None or library.shade.range is None
        else library.shade.range
    )
    problems += _problems(level, global_, "the material library's shade: ")
    looks = {}
    for name in sorted(library.materials):
        shade = library.materials[name].shade
        entry = _overlay(level, shade, library, ("materials", name, "shade"))
        problems += _problems(entry, level, f"material {shading.quote(name)}: ")
        own = {} if shade is None else dict(shade.given())
        looks[name] = _look(
            entry,
            own.get("range", fallback_range),
            {key: own.get(key, value) for key, value in capture.items()},
        )
    if problems:
        raise shading.ShadingError(problems)
    return Resolved(
        given,
        base,
        _look(level, fallback_range, capture),
        MappingProxyType(looks),
    )


def _overlay(parent, shade, library, path):
    """`parent`, the response leaves by path as `shading.Sourced`, with the
    leaves `shade` gives laid over them, each with its origin in `library`."""
    if shade is None:
        return parent
    level = dict(parent)
    for leaf, field in shading.FIELDS.items():
        value = getattr(shade, field)
        if value is not None:
            level[leaf] = shading.Sourced(
                value, library.origin((*path, *leaf.split(".")))
            )
    return level


def _problems(level, parent, prefix):
    """The cross-field problems of the response `level`, as messages starting
    with `prefix`. A rule whose contributing leaves are those of `parent`,
    the level above, is left to it."""
    budget = ("key.strength", "sky.strength", "ground.strength")
    order = ("brightness.floor", "brightness.ceiling")
    messages = []
    for leaves, check in (
        (budget, shading.budget_problem),
        (order, shading.brightness_problem),
    ):
        if parent is not None and all(level[leaf] == parent[leaf] for leaf in leaves):
            continue
        problem = check(*(level[leaf] for leaf in leaves))
        if problem is not None:
            messages.append(prefix + problem)
    return messages


def _look(level, shade_range, capture):
    return Look(
        shading.Response(
            **{field: level[path].value for path, field in shading.FIELDS.items()}
        ),
        tuple(shade_range),
        **capture,
    )
