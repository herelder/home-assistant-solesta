"""Typed integration and provider errors."""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for failures reported by a status provider."""


class ProviderAuthenticationError(ProviderError):
    """Authentication failed or an authenticated session expired."""


class ProviderCommunicationError(ProviderError):
    """The provider could not be reached or returned a temporary failure."""


class ProviderConfigurationError(ProviderError):
    """The persisted provider configuration is invalid or unsupported."""


class ProviderResponseError(ProviderError):
    """The provider response did not satisfy the configured response contract."""


class ProviderRateLimitError(ProviderCommunicationError):
    """The provider rejected a request because its rate limit was reached."""


class ProviderSystemError(ProviderError):
    """A request failed definitively for one source system."""
