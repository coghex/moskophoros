"""The shipped default shade, for tests that build capture settings."""

from moskophoros import settings
from moskophoros.capture import backend

DEFAULT_SHADE = backend.Shade(
    ao_distance_m=settings.DEFAULTS["shade.ao_distance_m"],
    ao_samples=settings.DEFAULTS["shade.ao_samples"],
    occlusion_weight=settings.DEFAULTS["shade.occlusion_weight"],
    convexity_weight=settings.DEFAULTS["shade.convexity_weight"],
)
DEFAULT_RANGE = settings.DEFAULTS["shade.range"]
