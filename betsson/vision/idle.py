"""Calibración de la animación de reposo de un juego, en cada ejecución.

Muchos juegos se mueven en reposo (agua, burbujas, brillos). Un umbral fijo de cambio de imagen confunde
esa animación con el inicio de una tirada, o no ve nunca la imagen quieta al terminar. Antes de girar se
miran unos fotogramas en reposo y los umbrales se ajustan a lo que se ha medido:

- inicio de tirada: el cambio respecto al primer fotograma tiene que superar con margen el del reposo;
- fin de tirada: el cambio entre fotogramas seguidos puede llegar al del reposo (eso cuenta como quieto).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from statistics import median

import numpy as np

from betsson.vision.diff import change_ratio

START_MARGIN = 2.0  # inicio = este múltiplo del mayor cambio de reposo respecto al primer fotograma
STABLE_MARGIN = 1.5  # quieto = hasta este múltiplo del mayor cambio de reposo entre fotogramas seguidos
MAX_START_THRESHOLD = 0.6  # por encima no se distinguiría una tirada de la animación: calibración no fiable


@dataclass(frozen=True)
class IdleCalibration:
    frames: int
    idle_max_vs_first: float  # mayor cambio respecto al primer fotograma (lo que compara spin)
    idle_max_step: float  # mayor cambio entre fotogramas seguidos (lo que compara wait_spin_end)
    idle_median_step: float
    start_threshold: float
    stable_threshold: float
    reliable: bool

    def summary(self) -> str:
        warning = "" if self.reliable else " (juego muy animado: calibración poco fiable)"
        return (
            f"reposo calibrado con {self.frames} fotogramas: cambio máx {self.idle_max_vs_first:.3f} "
            f"(entre seguidos máx {self.idle_max_step:.3f}, mediana {self.idle_median_step:.3f}) -> "
            f"umbral de inicio {self.start_threshold:.3f}, de estabilidad {self.stable_threshold:.3f}{warning}"
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def calibrate(frames: list[np.ndarray], profile_threshold: float) -> IdleCalibration:
    """Umbrales a partir de fotogramas en reposo. Nunca por debajo del umbral del perfil."""
    if len(frames) < 2:
        raise ValueError("hacen falta al menos 2 fotogramas para calibrar el reposo")
    first = frames[0]
    vs_first = [change_ratio(first, f) for f in frames[1:]]
    steps = [change_ratio(a, b) for a, b in zip(frames, frames[1:])]
    start = max(profile_threshold, START_MARGIN * max(vs_first))
    stable = max(profile_threshold, STABLE_MARGIN * max(steps))
    reliable = start <= MAX_START_THRESHOLD
    return IdleCalibration(
        frames=len(frames),
        idle_max_vs_first=round(max(vs_first), 4),
        idle_max_step=round(max(steps), 4),
        idle_median_step=round(median(steps), 4),
        start_threshold=round(min(start, MAX_START_THRESHOLD), 4),
        stable_threshold=round(min(stable, MAX_START_THRESHOLD), 4),
        reliable=reliable,
    )
