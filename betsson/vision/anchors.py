"""Localiza importes por su etiqueta visible (CREDIT/SALDO, BET/APUESTA, WIN/GANANCIA), no por posición.

Estrategia, en orden:
1. Caja que contiene la etiqueta y el número a la vez ("CREDIT 100,000.00 €").
2. Caja con número más cercana a la derecha de la etiqueta, en la misma fila.
3. Caja con número más cercana debajo de la etiqueta, en la misma columna.
La zona del perfil solo desempata (si hay varias etiquetas iguales, gana la que cae dentro).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from betsson.vision.ocr import TextBox, normalize

# Número con separadores de miles/decimales opcionales, con o sin símbolo alrededor.
_NUMBER = re.compile(r"\d[\d.,\s]*\d|\d")
_LEADING_WORD = re.compile(r"^[A-Z]{3,}")
# Máxima distancia, en alturas de la etiqueta, para aceptar un valor como "suyo".
_MAX_RIGHT_GAP = 12.0
_MAX_BELOW_GAP = 3.0


@dataclass(frozen=True)
class AnchoredValue:
    label: TextBox
    value_text: str  # texto en bruto del importe, con su símbolo si lo hay
    confidence: float
    strategy: str


def has_number(text: str) -> bool:
    return bool(_NUMBER.search(text))


def _is_bare_value(text: str) -> bool:
    """Un valor suelto empieza por número o símbolo; si empieza por palabra es otra etiqueta ('APUESTA 2,00 €')."""
    return has_number(text) and not _LEADING_WORD.match(normalize(text))


def _label_match(box: TextBox, aliases: list[str]) -> str | None:
    """Alias que aparece como palabra al principio de la caja (evita 'BET' dentro de 'BETSSON')."""
    norm = box.norm
    for alias in aliases:
        a = normalize(alias)
        if norm == a or re.match(rf"^{re.escape(a)}(?![A-Z])", norm):
            return a
    return None


def _strip_label(text: str, alias_norm: str) -> str:
    """Quita la etiqueta y los dos puntos del principio de la caja: 'CREDIT: 100 €' -> '100 €'."""
    norm = normalize(text)
    if not norm.startswith(alias_norm):
        return text
    # La normalización conserva la longitud salvo tildes combinadas: se corta por número de palabras.
    words = text.split()
    rest = words[len(alias_norm.split()):]
    return " ".join(rest).lstrip(":").strip()


def _distance_right(label: TextBox, box: TextBox) -> float | None:
    same_row = abs(box.cy - label.cy) <= max(label.height, box.height) * 0.7
    gap = box.x0 - label.x1
    if not same_row or gap < -label.height * 0.5:
        return None
    rel = gap / max(label.height, 1)
    return rel if rel <= _MAX_RIGHT_GAP else None


def _distance_below(label: TextBox, box: TextBox) -> float | None:
    overlap = min(label.x1, box.x1) - max(label.x0, box.x0)
    same_column = overlap > 0 or abs(box.cx - label.cx) <= max(label.x1 - label.x0, box.x1 - box.x0)
    gap = box.y0 - label.y1
    if not same_column or gap < -label.height * 0.3:
        return None
    rel = gap / max(label.height, 1)
    return rel if rel <= _MAX_BELOW_GAP else None


def _value_for(label: TextBox, alias_norm: str, boxes: list[TextBox]) -> AnchoredValue | None:
    inline = _strip_label(label.text, alias_norm)
    if has_number(inline):
        return AnchoredValue(label, inline, label.score, "inline")
    best: tuple[float, TextBox, str] | None = None
    for box in boxes:
        if box is label or not _is_bare_value(box.text):
            continue
        for strategy, dist in (("right", _distance_right(label, box)), ("below", _distance_below(label, box))):
            if dist is not None and (best is None or dist < best[0]):
                best = (dist, box, strategy)
    if best is None:
        return None
    _, box, strategy = best
    return AnchoredValue(label, box.text, min(label.score, box.score), strategy)


def find_amount(
    boxes: list[TextBox],
    aliases: list[str],
    hint: tuple[int, int, int, int] | None = None,
) -> AnchoredValue | None:
    """Importe asociado a la primera etiqueta reconocida. hint = (x0, y0, x1, y1) en píxeles, solo para desempatar."""
    candidates: list[AnchoredValue] = []
    for box in boxes:
        alias = _label_match(box, aliases)
        if alias is None:
            continue
        value = _value_for(box, alias, boxes)
        if value is not None:
            candidates.append(value)
    if not candidates:
        return None
    if hint is not None and len(candidates) > 1:
        x0, y0, x1, y1 = hint
        inside = [c for c in candidates if x0 <= c.label.cx <= x1 and y0 <= c.label.cy <= y1]
        if inside:
            candidates = inside
    return max(candidates, key=lambda c: c.confidence)
