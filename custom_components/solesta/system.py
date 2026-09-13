"""Provider-independent system model."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from .provider import Provider


class System:
    """Bind one integration system to one provider source-system ID."""

    def __init__(
        self,
        system_uid: str,
        system_id: str,
        source_system_id: str,
        provider: Provider,
    ) -> None:
        for field, value in (
            ("system_uid", system_uid),
            ("system_id", system_id),
            ("source_system_id", source_system_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field} must be a non-empty string")

        self._system_uid = system_uid
        self._system_id = system_id
        self._source_system_id = source_system_id
        self._provider = provider

    @property
    def system_uid(self) -> str:
        """Return the permanent UUID identity of this system instance."""
        return self._system_uid

    @property
    def system_id(self) -> str:
        """Return the immutable technical name of this system instance."""
        return self._system_id

    @property
    def source_system_id(self) -> str:
        """Return the provider's identifier for this system."""
        return self._source_system_id

    @property
    def provider(self) -> Provider:
        """Return the bound status provider."""
        return self._provider

    async def status(
        self,
        source_keys: Collection[str],
    ) -> dict[str, Any]:
        """Return source values required by the runtime configuration."""
        return await self._provider.get_system_status(
            self._source_system_id,
            source_keys,
        )

    @property
    def info(self) -> dict[str, Any]:
        """Return provider profile data supplemented with local identities."""
        info = self._provider.profile
        info.update(
            {
                "system_uid": self._system_uid,
                "system_id": self._system_id,
                "source_system_id": self._source_system_id,
            }
        )
        return info
