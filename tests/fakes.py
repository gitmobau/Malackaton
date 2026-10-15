"""Simulaciones de A (BetssonSite) y B (GameEyes, perfiles) para probar los escenarios sin red.

Cada fake cumple el Protocol de betsson.core. Los importes van guionizados:
cada read_balance() devuelve la siguiente lectura de la lista.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

from betsson.core import (
    BetTarget,
    GameOpenError,
    IntroScreen,
    MarketContext,
    Message,
    Money,
    PlayMode,
    ProviderProfile,
    ProviderUIChanged,
    Reading,
    Rect,
    SpinEnd,
    SpinEndSignal,
)


@dataclass(frozen=True)
class FakeMarket:
    id: str = "es"
    currency_code: str = "EUR"
    language: str = "es"
    money_tolerance: Decimal = Decimal("0.01")
    min_bet: Decimal = Decimal("0.10")


def reading(amount: str | None, currency: str = "EUR", *, seen: bool = True, text: str | None = None,
            evidence: Path | None = None) -> Reading:
    """Lectura simulada. amount=None = OCR dudoso."""
    if amount is None:
        return Reading(raw_text=text or "?,??", confidence=0.3, reason="OCR dudoso", evidence_path=evidence)
    raw = text or (f"{amount} €" if seen and currency == "EUR" else amount)
    return Reading(raw_text=raw, money=Money(amount=Decimal(amount), currency=currency), currency_seen=seen,
                   confidence=0.98, evidence_path=evidence)


def _png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), (30, 30, 60)).save(path)
    return path


@dataclass
class FakeGameHandle:
    iframe_url: str = "https://games.example.test/fake-provider/slot?mode=real"
    play_mode: PlayMode = "real"
    play_mode_reason: str | None = "Betsson pidió los límites de sesión del regulador"
    evidence: tuple[Path, ...] = ()
    frame: np.ndarray | None = None  # canvas simulado; None = negro
    notices: tuple = ()

    def capture(self) -> np.ndarray:
        return self.frame if self.frame is not None else np.zeros((36, 64, 3), dtype=np.uint8)


@dataclass
class FakeBetssonSite:
    balances: list[Reading]
    out_dir: Path
    logged_in: bool = True
    handle: FakeGameHandle = field(default_factory=FakeGameHandle)
    login_assisted: bool = False
    login_assisted_at: datetime | None = None
    open_error: str | None = None

    def login(self) -> bool:
        return self.logged_in

    def is_logged_in(self) -> bool:
        return self.logged_in

    def read_balance(self) -> Reading:
        current = self.balances.pop(0) if self.balances else reading(None)
        shot = self.screenshot(f"betsson_balance_{len(self.balances)}")
        return current.model_copy(update={"evidence_path": shot})

    def open_game(self, slug: str) -> FakeGameHandle:
        if self.open_error:
            raise GameOpenError(self.open_error)
        return self.handle

    def screenshot(self, name: str) -> Path:
        return _png(self.out_dir / f"{name}.png")


@dataclass
class FakeProfile:
    name: str = "fake-provider"
    intro_screens: list[IntroScreen] = field(default_factory=list)
    labels: dict = field(default_factory=lambda: {"balance": {"es": ["saldo"]}, "bet": {"es": ["apuesta"]}, "win": {"es": ["ganancia"]}})
    hint_zones: dict = field(default_factory=lambda: {"balance": Rect(x=0.0, y=0.9, w=0.3, h=0.1)})
    spin_templates: list[Path] = field(default_factory=list)
    spin_hint: Rect = field(default_factory=lambda: Rect(x=0.45, y=0.8, w=0.1, h=0.1))
    insufficient_texts: dict = field(default_factory=lambda: {"es": ["saldo insuficiente"], "en": ["insufficient funds"]})
    spin_end: SpinEndSignal = field(default_factory=SpinEndSignal)
    network_pattern: str | None = None

    def detect(self, iframe_url: str, frame: np.ndarray | None) -> float:
        return 0.9


@dataclass
class FakeRegistry:
    profile: FakeProfile = field(default_factory=FakeProfile)
    drift: str | None = None  # si se fija, ensure_recognized lanza ProviderUIChanged

    def resolve(self, iframe_url: str, frame: np.ndarray | None) -> ProviderProfile:
        return self.profile

    def ensure_recognized(self, profile: ProviderProfile, frame: np.ndarray | None) -> None:
        if self.drift:
            raise ProviderUIChanged(self.drift)


@dataclass
class FakeGameEyes:
    """Ojos guionizados: balances en orden (antes, después), apuesta, ganancia y tirada."""

    profile: ProviderProfile
    out_dir: Path
    balances: list[Reading]
    bet: Reading
    win: Reading = field(default_factory=lambda: reading("0.00"))
    spin_starts: bool = True
    spin_end: SpinEnd = field(default_factory=lambda: SpinEnd(completed=True, duration_s=3.2))
    message: Message = field(default_factory=Message)
    fail_on_spin: Exception | None = None
    bets_set: list[BetTarget] = field(default_factory=list)
    step_bet: Reading | None = None  # apuesta visible tras set_bet("one_step")
    bet_targets: tuple[str, ...] = ("min", "above_balance", "one_step")

    def _shot(self, r: Reading, name: str) -> Reading:
        return r.model_copy(update={"evidence_path": self.screenshot(name)})

    def read_balance(self) -> Reading:
        current = self.balances.pop(0) if self.balances else reading(None)
        return self._shot(current, f"game_balance_{len(self.balances)}")

    def read_bet(self) -> Reading:
        return self._shot(self.bet, "game_bet")

    def read_win(self) -> Reading:
        return self._shot(self.win, "game_win")

    def set_bet(self, target: BetTarget) -> Reading:
        self.bets_set.append(target)
        if target == "one_step" and self.step_bet is not None:
            self.bet = self.step_bet
        return self.read_bet()

    def spin(self) -> bool:
        if self.fail_on_spin:
            raise self.fail_on_spin
        return self.spin_starts

    def wait_spin_end(self) -> SpinEnd:
        return self.spin_end.model_copy(update={"evidence_path": self.screenshot("spin_end")})

    def read_message(self) -> Message:
        return self.message.model_copy(update={"evidence_path": self.screenshot("message")})

    def screenshot(self, name: str) -> Path:
        return _png(self.out_dir / f"{name}.png")


def factory(eyes: FakeGameEyes) -> Callable[..., FakeGameEyes]:
    """GameEyesFactory que devuelve siempre los mismos ojos guionizados."""
    def make(handle: FakeGameHandle, profile: ProviderProfile, market: MarketContext) -> FakeGameEyes:
        return eyes
    return make
