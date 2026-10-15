"""Web de Betsson: cookies, login, saldo y apertura de juegos."""
from betsson.site.betsson_site import (
    Account,
    BetssonSite,
    GameHandle,
    GameInfo,
    GameLaunchError,
    GameNotFoundError,
    LoginError,
    SiteError,
)
from betsson.site.credentials import Credentials, MissingCredentialsError, credentials_for
from betsson.site.tracing import NoTrace, SegmentedTrace, TraceControl, trace_paused

__all__ = [
    "Account",
    "BetssonSite",
    "Credentials",
    "GameHandle",
    "GameInfo",
    "GameLaunchError",
    "GameNotFoundError",
    "LoginError",
    "MissingCredentialsError",
    "NoTrace",
    "SegmentedTrace",
    "SiteError",
    "TraceControl",
    "credentials_for",
    "trace_paused",
]
