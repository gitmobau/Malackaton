"""Localiza importes por su etiqueta visible (CREDIT/SALDO, BET/APUESTA, WIN/GANANCIA), no por posición.

Estrategia, en orden:
1. Caja que contiene la etiqueta y solo un importe a continuación ("CREDIT 100,000.00 €").
2. Caja con importe más cercana a la derecha de la etiqueta, en la misma fila.
3. Caja con importe más cercana debajo de la etiqueta, en la misma columna.
Un valor que otra etiqueta tiene igual o más cerca no se asigna (no se roba el importe de otro campo).
La zona del perfil solo desempata (si hay varias etiquetas iguales, gana la que cae dentro).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from betsson.vision.ocr import TextBox, normalize

# Número con separadores de miles/decimales opcionales.
_NUMBER = re.compile(r"\d[\d.,]*\d|\d")
_LEADING_WORD = re.compile(r"^[A-Z]{3,}")
# Un importe admite como mucho un código o símbolo de moneda con letras ("EUR", "S/", "PEN").
_MAX_LETTERS_IN_VALUE = 3
# Máxima distancia, en alturas de la etiqueta, para aceptar un valor como "suyo".
_MAX_RIGHT_GAP = 6.0
_MAX_BELOW_GAP = 2.0
_ADJACENT_GAP = 1.0  # un importe a menos de una altura de la caja de la etiqueta va "pegado" a ella


@dataclass(frozen=True)
class AnchoredValue:
    label: TextBox
    value_text: str  # texto en bruto del importe, con su símbolo si lo hay
    confidence: float
    strategy: str
    value_box: TextBox  # caja donde está el importe (la de la etiqueta si es "inline")


def has_number(text: str) -> bool:
    return bool(_NUMBER.search(text))


def is_bare_value(text: str) -> bool:
    """Solo un importe: número con su símbolo o código de moneda. 'APUESTA 2,00 €', '10 FREE' o 'X2 MAX' no."""
    norm = normalize(text)
    letters = sum(c.isalpha() for c in norm)
    return has_number(norm) and not _LEADING_WORD.match(norm) and letters <= _MAX_LETTERS_IN_VALUE


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
    stripped = text.strip()
    # Se corta por caracteres (no por palabras): 'Saldo:25000.00' no lleva espacio tras la etiqueta.
    # normalize() quita tildes sin cambiar el número de letras, así que el prefijo mide lo mismo.
    if normalize(stripped[: len(alias_norm)]) != alias_norm:
        return text
    return stripped[len(alias_norm):].lstrip(" :").strip()


def _distance_right(label: TextBox, box: TextBox) -> float | None:
    same_row = abs(box.cy - label.cy) <= max(label.height, box.height) * 0.7
    gap = box.x0 - label.x1
    # Las cajas del OCR se solapan a menudo (real: 'CRÉDITO' hasta x=274 y '99,90 €' desde x=262):
    # basta con que el centro del valor quede a la derecha del final de la etiqueta.
    if not same_row or box.cx <= label.x1:
        return None
    rel = max(0.0, gap / max(label.height, 1))
    return rel if rel <= _MAX_RIGHT_GAP else None


def _distance_below(label: TextBox, box: TextBox) -> float | None:
    overlap = min(label.x1, box.x1) - max(label.x0, box.x0)
    same_column = overlap > 0 or abs(box.cx - label.cx) <= max(label.x1 - label.x0, box.x1 - box.x0)
    gap = box.y0 - label.y1
    if not same_column or gap < -label.height * 0.3:
        return None
    rel = max(0.0, gap / max(label.height, 1))
    return rel if rel <= _MAX_BELOW_GAP else None


_STRATEGIES = (("right", _distance_right), ("below", _distance_below))  # en orden de preferencia


def _owned_by_other_label(
    value: TextBox, label: TextBox, own_rank: int, own_distance: float, boxes: list[TextBox]
) -> bool:
    """True si otra etiqueta (caja que empieza por palabra) reclama ese valor con mejor derecho:
    con una estrategia preferente (a la derecha gana a debajo) o con la misma y a igual o menor distancia."""
    for other in boxes:
        if other is label or other is value or not _LEADING_WORD.match(other.norm):
            continue
        for rank, (_, distance) in enumerate(_STRATEGIES):
            d = distance(other, value)
            if d is not None and (rank < own_rank or (rank == own_rank and d <= own_distance)):
                return True
    return False


def _value_for(label: TextBox, alias_norm: str, boxes: list[TextBox]) -> AnchoredValue | None:
    inline = _strip_label(label.text, alias_norm)
    values = [b for b in boxes if b is not label and is_bare_value(b.text)]
    if inline:
        # Algo detrás de la etiqueta en la misma caja: solo vale si es un importe ('WIN UP TO 5.000 €' no).
        if not is_bare_value(inline):
            return None
        # Si además hay un importe pegado a la derecha ('CRÉDITO 1' + '100,00 €', caso real), el OCR
        # ha partido o duplicado cifras: es ambiguo y se deja que GameEyes relea ampliando.
        if any((d := _distance_right(label, b)) is not None and d <= _ADJACENT_GAP for b in values):
            return None
        return AnchoredValue(label, inline, label.score, "inline", label)
    # La misma fila manda: "debajo" solo cuenta si no hay nada a la derecha (las líneas apiladas
    # como CRÉDITO/APUESTA tienen el valor de la siguiente justo debajo de la etiqueta).
    for rank, (strategy, distance) in enumerate(_STRATEGIES):
        scored = sorted(
            ((d, b) for b in values if (d := distance(label, b)) is not None), key=lambda pair: pair[0]
        )
        for d, box in scored:
            if not _owned_by_other_label(box, label, rank, d, boxes):
                return AnchoredValue(label, box.text, min(label.score, box.score), strategy, box)
    return None


def bare_values(boxes: list[TextBox]) -> list[TextBox]:
    """Cajas que son solo un importe, de izquierda a derecha."""
    return sorted((b for b in boxes if is_bare_value(b.text)), key=lambda b: b.x0)


def find_label(boxes: list[TextBox], aliases: list[str]) -> TextBox | None:
    """Primera caja que es la etiqueta (tenga o no importe legible al lado)."""
    return next((b for b in boxes if _label_match(b, aliases) is not None), None)


def find_amount(
    boxes: list[TextBox],
    aliases: list[str],
    hint: tuple[int, int, int, int] | None = None,
) -> AnchoredValue | None:
    """Importe asociado a la etiqueta reconocida. hint = (x0, y0, x1, y1) en píxeles, solo para desempatar."""
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
        if not inside:
            # Varias etiquetas iguales (p. ej. apuesta en monedas y en dinero) y ninguna donde dice el
            # perfil: elegir una sería adivinar. No concluyente.
            return None
        candidates = inside
    return max(candidates, key=lambda c: c.confidence)
