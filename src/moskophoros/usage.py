"""The usage error of the export preparation, in one place so its modules
share it: settings or paths the command cannot honor, found before capture
(design §Exit codes)."""

from moskophoros.fit import USAGE_ERROR


class UsageError(Exception):
    """A configuration that cannot be resolved: exit classification 2."""

    exit_code = USAGE_ERROR
