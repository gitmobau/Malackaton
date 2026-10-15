"""Carga y valida los mercados de config/markets/*.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from betsson.market.schema import Market

MARKETS_DIR = Path(__file__).resolve().parents[2] / "config" / "markets"


class UnknownMarketError(LookupError):
    pass


def list_markets(markets_dir: Path = MARKETS_DIR) -> list[str]:
    return sorted(p.stem for p in markets_dir.glob("*.json"))


@lru_cache(maxsize=None)
def load_market(market_id: str, markets_dir: Path = MARKETS_DIR) -> Market:
    path = markets_dir / f"{market_id}.json"
    if not path.is_file():
        raise UnknownMarketError(f"mercado '{market_id}' sin configurar; disponibles: {list_markets(markets_dir)}")
    market = Market.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if market.id != market_id:
        raise ValueError(f"{path.name}: el id interno '{market.id}' no coincide con el nombre del archivo")
    return market
