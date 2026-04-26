from __future__ import annotations

import keyring
import keyring.errors

_SERVICE = "sparkd"


def _backend_set(service: str, key: str, value: str) -> None:
    keyring.set_password(service, key, value)


def _backend_get(service: str, key: str) -> str | None:
    return keyring.get_password(service, key)


def _backend_delete(service: str, key: str) -> None:
    try:
        keyring.delete_password(service, key)
    except keyring.errors.PasswordDeleteError:
        pass


def set_secret(key: str, value: str) -> None:
    _backend_set(_SERVICE, key, value)


def get_secret(key: str) -> str | None:
    return _backend_get(_SERVICE, key)


def delete_secret(key: str) -> None:
    _backend_delete(_SERVICE, key)
