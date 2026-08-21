"""Error taxonomy.

Adapters wrap vendor exceptions in AdapterError so domain code never catches a
transport type, and a failing vendor can never be mistaken for a failing document.
"""


class SignetError(Exception):
    """Base for every error this package raises."""


class PayloadError(SignetError):
    """A payload could not be built or parsed."""


class MarkError(SignetError):
    """A mark could not be encoded or decoded."""


class ConfigError(SignetError):
    """Configuration is missing or malformed."""


class AdapterError(SignetError):
    """An external service failed. Never raised by core."""
