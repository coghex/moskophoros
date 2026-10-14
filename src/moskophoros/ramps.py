"""Generated ramps: a base colour and a band count made into palette indices
(material styling design D-28, D-33 and its numerical reference).

Band `i` of `N` (0 the darkest) is `k = N − 1 − i` shades below the base, so
the last band is the base colour itself. Each shade lowers OKLab lightness by
`step`, turns the hue by `hue` degrees (a near-grey keeps its hue) and fades
the chroma linearly by `fade` at the darkest; a shade outside the sRGB gamut
loses chroma, never lightness or hue; and each snaps to the nearest palette
entry in OKLab, equal distances keeping the lower index. Everything here is
pure and uses the OKLab conversion palette mapping uses.
"""

import math

import numpy as np

from moskophoros import imageops

# A base colour with less OKLab chroma than this keeps its hue.
GREY_CHROMA = 0.02
# How far outside [0, 1] a linear channel may stray and still be in gamut.
GAMUT_TOLERANCE = 1e-6
# The halvings of [0, C] that find a shade's largest chroma in gamut.
HALVINGS = 40


def oklab(colors):
    """The OKLab of each sRGB colour in `colors`, as palette mapping computes
    it: an `(n, 3)` `float64` array."""
    return imageops._oklab(np.asarray(colors, dtype=np.uint8).reshape(-1, 3))


def in_gamut(lightness, a, b):
    """Whether OKLab `(L, a, b)` is in the sRGB gamut: every linear channel,
    by the inverse of Björn Ottosson's 2021 matrices, within `[−10⁻⁶,
    1 + 10⁻⁶]`."""
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    channels = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    return all(
        -GAMUT_TOLERANCE <= channel <= 1 + GAMUT_TOLERANCE for channel in channels
    )


def _ab(chroma, hue_deg):
    radians = hue_deg * math.pi / 180
    return chroma * math.cos(radians), chroma * math.sin(radians)


def shades(base, bands, step, hue, fade):
    """The OKLab `(L, a, b)` of each band, darkest first, before snapping.

    `base` is an sRGB `(r, g, b)` of bytes, `bands` the band count N, and
    `step`, `hue` and `fade` the lightness step, hue shift in degrees and
    chroma fade.
    """
    lightness, a0, b0 = (float(value) for value in oklab([base])[0])
    chroma = math.hypot(a0, b0)
    hue0 = math.degrees(math.atan2(b0, a0))
    result = []
    for band in range(bands):
        k = bands - 1 - band
        level = max(0.0, lightness - step * k)
        angle = hue0 if chroma < GREY_CHROMA else hue0 + hue * k
        amount = chroma if bands == 1 else chroma * (1 - fade * k / (bands - 1))
        if not in_gamut(level, *_ab(amount, angle)):
            low, high = 0.0, amount
            for _ in range(HALVINGS):
                middle = (low + high) / 2
                if in_gamut(level, *_ab(middle, angle)):
                    low = middle
                else:
                    high = middle
            amount = low
        result.append((level, *_ab(amount, angle)))
    return result


def snap(shade, palette_lab):
    """The index of the palette entry nearest OKLab `shade`, by the sum of
    squared differences; a later entry wins only when strictly nearer."""
    lightness, a, b = shade
    best, nearest = 0, None
    for index, (entry_l, entry_a, entry_b) in enumerate(palette_lab):
        distance = (
            (lightness - float(entry_l)) ** 2
            + (a - float(entry_a)) ** 2
            + (b - float(entry_b)) ** 2
        )
        if nearest is None or distance < nearest:
            best, nearest = index, distance
    return best


def generate(base, bands, step, hue, fade, colors):
    """The ramp's `bands` palette indices, darkest first, into the palette
    `colors` (sRGB triples). Repeats are kept, so the band count never
    changes."""
    palette_lab = oklab(colors)
    return tuple(
        snap(shade, palette_lab) for shade in shades(base, bands, step, hue, fade)
    )
