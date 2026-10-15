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
from betsson.core.interfaces import INCONCLUSIVE_PREFIX, EvidencePath

Status = Literal["PASS", "FAIL"]
# Resumen para informe y CI: distingue un FAIL real de lo no concluyente.
Outcome = Literal["PASS", "FAIL", "INCONCLUSIVE", "PROVIDER_UI_CHANGED"]
UI_CHANGED_PREFIX = f"{PROVIDER_UI_CHANGED}: "
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
    evidence: tuple[EvidencePath, ...] = ()

    @model_validator(mode="after")
    def _coherent(self) -> CheckResult:
        if self.status == "PASS" and self.failure_kind is not None:
            raise ValueError("un PASS no lleva failure_kind")
        if self.status == "FAIL" and self.failure_kind is None:
            raise ValueError("un FAIL necesita failure_kind")
        if not self.reason.strip():
            raise ValueError("reason no puede estar vacío")
        prefixes = {FailureKind.INCONCLUSIVE: INCONCLUSIVE_PREFIX, FailureKind.PROVIDER_UI_CHANGED: UI_CHANGED_PREFIX}
        expected = prefixes.get(self.failure_kind) if self.failure_kind else None
        if expected and not self.reason.startswith(expected):
            raise ValueError(f"el motivo debe empezar por {expected!r}")
        if self.failure_kind is FailureKind.INTEGRATION and self.reason.startswith(tuple(prefixes.values())):
            raise ValueError("un fallo de integración no puede llevar prefijo de no concluyente")
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
            reason=why if why.startswith(UI_CHANGED_PREFIX) else UI_CHANGED_PREFIX + why,
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
    error: str | None = None  # la ejecución se cortó (timeout, crash del navegador…): el run es FAIL
    evidence: tuple[EvidencePath, ...] = ()  # vídeo, traza, capturas generales (relativas al run)

    @model_validator(mode="after")
    def _valid_checks(self) -> RunResult:
        ids = [r.id for r in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("comprobación repetida en results")
        foreign = [i.value for i in ids if i not in SCENARIO_CHECKS[self.scenario]]
        if foreign:
            raise ValueError(f"comprobaciones que no son de {self.scenario.value}: {foreign}")
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
        return "PASS" if self.outcome == "PASS" else "FAIL"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def outcome(self) -> Outcome:
        """FAIL si hay un fallo de integración o un error; si no, PROVIDER_UI_CHANGED,
        luego INCONCLUSIVE (incluye comprobaciones sin resultado) y por último PASS."""
        kinds = {r.failure_kind for r in self.results}
        if self.error or FailureKind.INTEGRATION in kinds:
            return "FAIL"
        if FailureKind.PROVIDER_UI_CHANGED in kinds:
            return "PROVIDER_UI_CHANGED"
        if FailureKind.INCONCLUSIVE in kinds or self.missing_checks:
            return "INCONCLUSIVE"
        return "PASS"

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
        run = cls.model_validate_json(path.read_text(encoding="utf-8"))
        if run.schema_version != SCHEMA_VERSION:
            raise ValueError(f"results.json con schema_version {run.schema_version}; se esperaba {SCHEMA_VERSION}")
        return run
