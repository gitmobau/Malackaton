"""GameEyesFactory de B (cumple betsson.core.GameEyesFactory): run_scenario la recibe inyectada."""
from __future__ import annotations

from pathlib import Path

from betsson.core import GameHandle, MarketContext
from betsson.game.eyes import GameEyes
from betsson.game.sources import HandleFrameSource
from betsson.profiles.base import ProfileSpec


class GameEyesFactory:
    """make(handle, profile, market) -> GameEyes. evidence_dir: dónde guardar las capturas del juego."""

    def __init__(self, evidence_dir: Path | None = None) -> None:
        self.evidence_dir = evidence_dir

    def __call__(self, handle: GameHandle, profile: ProfileSpec, market: MarketContext) -> GameEyes:
        eyes = GameEyes(HandleFrameSource(handle), profile, market, evidence_dir=self.evidence_dir)
        eyes.dismiss_intro()
        return eyes


make_game_eyes = GameEyesFactory()
