"""Resultados: CheckResult (una comprobación) y RunResult (results.json de un escenario).

Reglas:
- Solo hay PASS o FAIL. Lo dudoso es FAIL con failure_kind="inconclusive"
  y un motivo que empieza por "inconclusive: ". Nunca un PASS optimista.
- Si el perfil no reconoce el juego, FAIL con failure_kind="provider_ui_changed":
  es un aviso de mantenimiento, no un fallo de integración.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from betsson.core.errors import PROVIDER_UI_CHANGED
from betsson.core.ids import SCENARIO_CHECKS, CheckId, Scenario

Status = Literal["PASS", "FAIL"]
INCONCLUSIVE_PREFIX = "inconclusive: "
SCHEMA_VERSION = 1


class FailureKind(str, Enum):
    INTEGRATION = "integration"  # FAIL real: saldo que no cuadra, tirada no rechazada…
    INCONCLUSIVE = "inconclusive"  # no se pudo leer o verificar con seguridad
    PROVIDER_UI_CHANGED = "provider_ui_changed"  # el perfil no reconoce el juego


class CheckResult(BaseModel):
    """Resultado de una comprobación. Usa los constructores passed/failed/inconclusive/ui_changed."""

    model_config = ConfigDict(frozen=True)

    id: CheckId
    status: Status
    reason: str
    failure_kind: FailureKind | None = None
    expected: str | None = None
    observed: str | None = None
    evidence: tuple[Path, ...] = ()

    @model_validator(mode="after")
    def _coherent(self) -> CheckResult:
        if self.status == "PASS" and self.failure_kind is not None:
            raise ValueError("un PASS no lleva failure_kind")
        if self.status == "FAIL" and self.failure_kind is None:
            raise ValueError("un FAIL necesita failure_kind")
        if not self.reason.strip():
            raise ValueError("reason no puede estar vacío")
        if self.failure_kind is FailureKind.INCONCLUSIVE and not self.reason.startswith(INCONCLUSIVE_PREFIX):
            raise ValueError(f"un no concluyente debe empezar por {INCONCLUSIVE_PREFIX!r}")
        return self

    @classmethod
    def passed(cls, id: CheckId, reason: str, **extra: Any) -> CheckResult:
        return cls(id=id, status="PASS", reason=reason, **extra)

    @classmethod
    def failed(cls, id: CheckId, reason: str, **extra: Any) -> CheckResult:
        return cls(id=id, status="FAIL", reason=reason, failure_kind=FailureKind.INTEGRATION, **extra)

    @classmethod
    def inconclusive(cls, id: CheckId, why: str, **extra: Any) -> CheckResult:
        reason = why if why.startswith(INCONCLUSIVE_PREFIX) else INCONCLUSIVE_PREFIX + why
        return cls(id=id, status="FAIL", reason=reason, failure_kind=FailureKind.INCONCLUSIVE, **extra)

    @classmethod
    def ui_changed(cls, id: CheckId, why: str, **extra: Any) -> CheckResult:
        return cls(
            id=id,
            status="FAIL",
            reason=f"{PROVIDER_UI_CHANGED}: {why}",
            failure_kind=FailureKind.PROVIDER_UI_CHANGED,
            **extra,
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunResult(BaseModel):
    """Un escenario en un mercado: lo que se escribe en results.json."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    run_id: str
    market: str
    scenario: Scenario
    provider: str | None = None  # nombre del perfil detectado; None si no se llegó a abrir el juego
    game: str | None = None  # slug del juego
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    results: tuple[CheckResult, ...] = ()
    warnings: tuple[str, ...] = ()  # p. ej. "PROVIDER_UI_CHANGED: …", "mercado configurado sin cuenta"
    evidence: tuple[Path, ...] = ()  # vídeo, traza, capturas generales

    @model_validator(mode="after")
    def _no_duplicates(self) -> RunResult:
        ids = [r.id for r in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("comprobación repetida en results")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing_checks(self) -> list[CheckId]:
        """Comprobaciones del escenario sin resultado: cuentan como FAIL del escenario."""
        done = {r.id for r in self.results}
        return [c for c in SCENARIO_CHECKS[self.scenario] if c not in done]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict(self) -> Status:
        ok = bool(self.results) and not self.missing_checks and all(r.status == "PASS" for r in self.results)
        return "PASS" if ok else "FAIL"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def provider_ui_changed(self) -> bool:
        return any(r.failure_kind is FailureKind.PROVIDER_UI_CHANGED for r in self.results)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> RunResult:
        data = cls.model_validate_json(path.read_text(encoding="utf-8"))
        return data
