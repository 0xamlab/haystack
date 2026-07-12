from __future__ import annotations

from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    """Process-local keyring for subprocess integration tests only."""

    priority = 1
    _values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._values.pop((service, username), None)
