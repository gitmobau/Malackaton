"""Credenciales de las cuentas de prueba: solo desde variables de entorno (.env en local, Secrets en CI).

Nunca se imprimen: el repr de Credentials las oculta.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from betsson.market.schema import Market

_REPO_ROOT = Path(__file__).resolve().parents[2]
# .env del worktree y, si no está, el compartido de la carpeta de arriba (modo de un portátil).
_DOTENV_CANDIDATES = (_REPO_ROOT / ".env", _REPO_ROOT.parent / ".env")


class MissingCredentialsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Credentials:
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return "Credentials(<oculto>)"


def _load_dotenv_files() -> None:
    for path in _DOTENV_CANDIDATES:
        if path.is_file():
            load_dotenv(path, override=False)


def credentials_for(market: Market, *, insufficient_funds: bool = False) -> Credentials:
    """Lee las credenciales del mercado. Lanza MissingCredentialsError con los NOMBRES de las variables que faltan."""
    _load_dotenv_files()
    env = market.credentials_env
    user_var, pass_var = (
        (env.username_insufficient, env.password_insufficient) if insufficient_funds else (env.username, env.password)
    )
    if not user_var or not pass_var:
        raise MissingCredentialsError(f"el mercado '{market.id}' no tiene configurada la cuenta sin saldo")
    missing = [name for name in (user_var, pass_var) if not os.environ.get(name)]
    if missing:
        raise MissingCredentialsError(f"faltan variables de entorno: {', '.join(missing)} (ponlas en .env)")
    return Credentials(username=os.environ[user_var], password=os.environ[pass_var])
