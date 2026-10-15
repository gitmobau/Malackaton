"""GameEyes: mira el canvas del juego como un jugador (cumple betsson.core.GameEyes).

No conoce ningún proveedor: todo sale del perfil. Reglas:
- La prueba es lo visible (OCR, plantillas, cambio de imagen). Un clic nunca es prueba.
- Lo dudoso devuelve money=None / completed=False / matches_insufficient=None con reason "inconclusive: …".
- Si el perfil deja de reconocer el juego lo dice el registro (ensure_recognized), no GameEyes.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np

from betsson.core import BetTarget, GameField, MarketContext, Message, Money, Reading, SpinEnd
from betsson.game.money_reader import MoneyReader, money_reader_for
from betsson.game.sources import FrameSource
from betsson.profiles.base import Control, IntroStep, ProfileSpec
from betsson.vision.anchors import AnchoredValue, bare_values, find_amount, find_label
from betsson.vision.diff import change_ratio
from betsson.vision.geometry import center, contains, to_pixels
from betsson.vision.ocr import TextBox, full_text, normalize, read_text
from betsson.vision.template import find_template

# Si el OCR a tamaño real no encuentra una etiqueta, se reintenta ampliando (textos pequeños del canvas).
_UPSCALES: tuple[float, ...] = (1.0, 2.0)
_MAX_INTRO_STEPS = 6
_LOADING_TIMEOUT_S = 60.0
_REREAD_UPSCALE = 3.0
_TRUSTED_SCORE = 0.95  # por debajo de esta confianza del OCR, el importe se relee recortado
_MAX_BET_STEPS = 30  # pulsaciones máximas de +/- para llegar a la apuesta mínima o máxima
_DEFAULT_EVIDENCE_DIR = Path("outputs") / "evidence" / "game"


class GameEyes:
    def __init__(
        self,
        source: FrameSource,
        profile: ProfileSpec,
        market: MarketContext,
        money_reader: MoneyReader | None = None,
        evidence_dir: Path | None = None,
    ) -> None:
        self._source = source
        self.profile = profile
        self._market = market
        self._lang = market.language
        self._money = money_reader or money_reader_for(market)
        # Si es None, read_* no guardan evidencias; screenshot() usa la carpeta por defecto.
        self.evidence_dir = evidence_dir
        self.notes: list[str] = []  # qué tuvo que recalibrar o suponer: va al informe
        self._spin_started = False
        self._shots = 0  # numera las evidencias para que "antes" y "después" no se pisen

    # ---------- evidencias ----------

    def screenshot(self, name: str, frame: np.ndarray | None = None) -> Path:
        """Guarda el frame actual (o el dado) como evidencia y devuelve su ruta."""
        folder = self.evidence_dir or _DEFAULT_EVIDENCE_DIR
        folder.mkdir(parents=True, exist_ok=True)
        self._shots += 1
        path = folder / f"{self._shots:03d}_{name}.png"
        ok, png = cv2.imencode(".png", self._source.grab() if frame is None else frame)
        if not ok:
            raise OSError(f"no se pudo codificar la evidencia {path}")
        path.write_bytes(png.tobytes())  # imwrite falla en silencio con rutas no ASCII en Windows
        return path

    def _evidence(self, name: str, frame: np.ndarray) -> Path | None:
        return self.screenshot(name, frame) if self.evidence_dir is not None else None

    # ---------- importes ----------

    def read_balance(self, frame: np.ndarray | None = None) -> Reading:
        return self.read_amount("balance", frame)

    def read_bet(self, frame: np.ndarray | None = None) -> Reading:
        return self.read_amount("bet", frame)

    def read_win(self, frame: np.ndarray | None = None) -> Reading:
        """Ganancia visible. Llamar tras wait_spin_end().

        Si el perfil declara que la ganancia se oculta cuando es 0 (win_hidden_when_zero) y se ven el
        saldo y la apuesta pero no la etiqueta de ganancia, se lee 0. Si no, es inconclusive.
        """
        frame = self._source.grab() if frame is None else frame
        reading = self.read_amount("win", frame)
        if reading.ok or not self.profile.win_hidden_when_zero:
            return reading
        aliases = self.profile.label_aliases("win", self._lang)
        if any(find_label(read_text(frame, upscale=u), aliases) for u in _UPSCALES):
            return reading  # se ve la etiqueta pero no se lee el importe: no se supone nada
        balance, bet = self.read_amount("balance", frame), self.read_amount("bet", frame)
        if not (balance.ok and bet.ok):
            return reading
        return Reading(
            raw_text="",
            money=Money(amount=Decimal(0), currency=self._market.currency_code),
            currency_seen=False,
            confidence=min(balance.confidence, bet.confidence),
            evidence_path=reading.evidence_path,
            reason="sin etiqueta de ganancia con saldo y apuesta visibles: el perfil la oculta cuando es 0",
        )

    def read_amount(self, field: GameField, frame: np.ndarray | None = None) -> Reading:
        frame = self._source.grab() if frame is None else frame
        anchored = self._find(field, frame)
        evidence = self._evidence(f"read_{field}", frame)
        if anchored is None:
            aliases = self.profile.label_aliases(field, self._lang)
            return Reading(
                evidence_path=evidence,
                reason=f"no se ve la etiqueta de {field} ({', '.join(aliases[:4])})",
            )
        first = _Read(anchored.value_text, self._money.parse(anchored.value_text), anchored.confidence)
        if first.money is not None and first.score >= _TRUSTED_SCORE:
            text, money, reason = first.text, first.money, None
        else:  # lectura dudosa o ilegible: se relee solo el importe y tiene que confirmarse
            text, money, reason = _reconcile(first, self._reread_value(frame, anchored))
        return Reading(
            raw_text=text,
            money=money,
            currency_seen=money is not None and self._money.currency_seen(text),
            confidence=min(1.0, anchored.confidence) if money is not None else 0.0,
            evidence_path=evidence,
            reason=reason,
        )

    def _find(self, field: GameField, frame: np.ndarray) -> AnchoredValue | None:
        aliases = self.profile.label_aliases(field, self._lang)
        hint_rect = self.profile.hint_zones.get(field)
        height, width = frame.shape[:2]
        hint = to_pixels(hint_rect, width, height) if hint_rect else None
        for upscale in _UPSCALES:
            anchored = find_amount(read_text(frame, upscale=upscale), aliases, hint)
            if anchored is not None:
                return anchored
        return None

    def _reread_value(self, frame: np.ndarray, anchored: AnchoredValue) -> _Read | None:
        """Segunda lectura: solo el recorte del importe, ampliado. El OCR del frame entero corta mal a veces.

        En "inline" la caja es etiqueta + importe: se recorta entera y bare_values descarta la etiqueta.
        """
        box = anchored.value_box
        height, width = frame.shape[:2]
        # Margen vertical pequeño: en muchos juegos las líneas (saldo, apuesta) van pegadas.
        y0, y1 = max(0, box.y0 - box.height // 6), min(height, box.y1 + box.height // 6)
        x0, x1 = max(0, box.x0 - box.height // 2), min(width, box.x1 + box.height)
        crop = frame[y0:y1, x0:x1]
        if crop.size == 0:
            return None
        # Solo cajas a la altura de la lectura original (nunca la línea vecina).
        target_cy = box.cy - y0
        values = [b for b in bare_values(read_text(crop, upscale=_REREAD_UPSCALE)) if abs(b.cy - target_cy) < box.height / 2]
        if not values:
            return None
        best = min(values, key=lambda b: abs(b.cy - target_cy))
        return _Read(best.text, self._money.parse(best.text), best.score)

    # ---------- apuesta ----------

    def set_bet(self, target: BetTarget) -> Reading:
        """Pulsa - hasta la apuesta mínima ("min") o + hasta superar el saldo ("above_balance").

        Devuelve la apuesta visible al terminar. La apuesta "mínima" es la que ya no baja al pulsar -.
        """
        control = self.profile.bet_down if target == "min" else self.profile.bet_up
        if control is None:
            return Reading(reason=f"el perfil '{self.profile.name}' no tiene control para la apuesta '{target}'")
        going_down = target == "min"
        balance = self.read_balance() if not going_down else None
        current = self.read_bet()
        moved = False
        for _ in range(_MAX_BET_STEPS):
            if _above(current, balance) or not current.ok:
                return current
            found_by_template = self._press(control)
            after = self._read_bet_change(current)
            if not after.ok:
                return after
            if after.money == current.money:  # tope: el control ya no cambia la apuesta
                if moved or found_by_template:
                    break
                return _doubtful(current, "el control de apuesta no se localizó y la pulsación no cambió nada")
            if (after.money.amount < current.money.amount) != going_down:
                return _doubtful(after, f"la apuesta cambió en sentido contrario ({current.raw_text} -> {after.raw_text})")
            current, moved = after, True
        else:
            return _doubtful(current, f"la apuesta seguía cambiando tras {_MAX_BET_STEPS} pulsaciones")
        if going_down:
            return current
        return _doubtful(current, f"la apuesta máxima visible ({current.raw_text}) no supera el saldo")

    def _press(self, control: Control) -> bool:
        """Pulsa el control. Devuelve True si se localizó por plantilla dentro de su zona."""
        frame = self._source.grab()
        match = find_template(frame, control.templates) if control.templates else None
        # Una coincidencia fuera de la zona del control puede ser el botón opuesto (- frente a +).
        if match is not None and not contains(control.hint, match.center):
            match = None
        if match is None:
            self.notes.append("control de apuesta por pista de zona")
        self._source.click(*(match.center if match else center(control.hint)))
        return match is not None

    def _read_bet_change(self, previous: Reading) -> Reading:
        """Apuesta tras pulsar. Se lee dos veces si no cambió, por si el juego aún no la había repintado."""
        after = self.read_bet()
        return self.read_bet() if after.money == previous.money else after

    # ---------- inicio ----------

    def dismiss_intro(self) -> list[str]:
        """Cierra las pantallas de inicio que reconozca y espera a ver el juego listo (etiqueta de saldo).

        Devuelve las que cerró, en orden. Si el saldo no aparece a tiempo, lo deja en notes (el registro
        o la lectura dirán después que no se reconoce: nunca se supone que el juego está listo).
        """
        dismissed: list[str] = []
        start = time.monotonic()
        while time.monotonic() - start < _LOADING_TIMEOUT_S and len(dismissed) < _MAX_INTRO_STEPS:
            frame = self._source.grab()
            if self._find("balance", frame) is not None:
                return dismissed  # juego listo
            boxes = read_text(frame)
            text = normalize(full_text(boxes))
            screen = next(
                (s for s in self.profile.intro_screens if any(normalize(t) in text for t in s.match_texts)),
                None,
            )
            if screen is None:
                continue  # aún cargando: cada vuelta es una captura y un OCR, el ritmo lo marca la señal
            if screen.wait_only:
                self._wait_for_change(frame, _LOADING_TIMEOUT_S)
            else:
                self._source.click(*self._intro_target(screen, frame, boxes))
                self._wait_for_change(frame, self.profile.spin_end.start_timeout_s)
            dismissed.append(screen.name)
        self.notes.append("inconclusive: tras las pantallas de inicio no apareció el saldo del juego")
        return dismissed

    def _intro_target(self, screen: IntroStep, frame: np.ndarray, boxes: list[TextBox]) -> tuple[float, float]:
        """Botón para cerrar la intro: por texto, por plantilla y, en último caso, por la pista."""
        height, width = frame.shape[:2]
        if screen.click_text:
            box = _find_box(boxes, screen.click_text)
            if box is not None:
                return (box.cx / width, box.cy / height)
        if screen.template:
            match = find_template(frame, [screen.template])
            if match is not None:
                return match.center
        self.notes.append(f"intro '{screen.name}': botón no encontrado, se usó la pista")
        return center(screen.click)

    # ---------- tirada ----------

    def locate_spin(self, frame: np.ndarray | None = None) -> tuple[float, float]:
        """Centro del botón de girar en fracción: plantilla multiescala y, si no, la pista del perfil."""
        frame = self._source.grab() if frame is None else frame
        if self.profile.spin_templates:
            match = find_template(frame, self.profile.spin_templates)
            if match is not None:
                return match.center
            self.notes.append("botón de girar no encontrado por plantilla: se usa la pista de zona")
        return center(self.profile.spin_hint)

    def spin(self) -> bool:
        """Pulsa girar y devuelve True solo si se VE que la tirada empieza (cambio de imagen)."""
        before = self._source.grab()
        self._evidence("spin_before", before)
        self._source.click(*self.locate_spin(before))
        started = self._wait_for_change(before, self.profile.spin_end.start_timeout_s)
        if started is None and self.profile.spin_key:  # segundo intento, como haría un jugador
            self._source.press(self.profile.spin_key)
            self.notes.append(f"el clic no arrancó la tirada: se probó la tecla '{self.profile.spin_key}'")
            started = self._wait_for_change(before, self.profile.spin_end.start_timeout_s)
        if started is not None:
            self._evidence("spin_started", started)
        self._spin_started = started is not None
        return self._spin_started

    def wait_spin_end(self) -> SpinEnd:
        """Fin de tirada = `stable_frames` comparaciones seguidas sin cambio apreciable."""
        signal = self.profile.spin_end
        start = time.monotonic()
        if not self._spin_started:
            return SpinEnd(completed=False, reason="inconclusive: no se vio que la tirada empezara")
        self._spin_started = False
        previous = self._source.grab()
        stable = 0
        while time.monotonic() - start < signal.timeout_s:
            current = self._source.grab()
            stable = stable + 1 if change_ratio(previous, current) <= signal.diff_threshold else 0
            previous = current
            if stable >= signal.stable_frames and self._amounts_settled(start, signal.timeout_s):
                return SpinEnd(
                    completed=True,
                    duration_s=round(time.monotonic() - start, 2),
                    evidence_path=self._evidence("spin_end", self._source.grab()),
                )
        return SpinEnd(
            completed=False,
            duration_s=round(time.monotonic() - start, 2),
            reason=f"inconclusive: la imagen no se estabilizó en {signal.timeout_s}s",
            evidence_path=self._evidence("spin_timeout", previous),
        )

    def _amounts_settled(self, start: float, timeout_s: float) -> bool:
        """El contador de ganancia y el saldo pueden seguir subiendo con la imagen casi quieta (cambian pocos
        píxeles): la tirada solo acaba cuando dos lecturas seguidas de saldo y ganancia coinciden."""
        previous = self._amount_texts(self._source.grab())
        while time.monotonic() - start < timeout_s:
            current = self._amount_texts(self._source.grab())
            if current == previous:
                return True
            previous = current
        return False

    def _amount_texts(self, frame: np.ndarray) -> tuple[str | None, ...]:
        return tuple(a.value_text if (a := self._find(f, frame)) else None for f in ("balance", "win"))

    # ---------- mensajes ----------

    def read_message(self, frame: np.ndarray | None = None) -> Message:
        """Texto visible y si coincide con el aviso de saldo insuficiente de algún idioma del perfil."""
        frame = self._source.grab() if frame is None else frame
        evidence = self._evidence("message", frame)
        boxes = read_text(frame)
        if not boxes:
            return Message(evidence_path=evidence, reason="inconclusive: no se pudo leer texto en pantalla")
        text = full_text(boxes)
        norm = normalize(text)
        confidence = min(b.score for b in boxes)
        langs = [self._lang] + [lang for lang in self.profile.insufficient_texts if lang != self._lang]
        for lang in langs:
            if any(normalize(t) in norm for t in self.profile.insufficient_texts.get(lang, [])):
                # La evidencia ya está guardada: se cierra la ventana para que no tape los importes.
                reason = self._dismiss_message(frame, boxes)
                return Message(
                    text=text, lang_detected=lang, matches_insufficient=True,
                    confidence=confidence, evidence_path=evidence, reason=reason,
                )
        return Message(text=text, matches_insufficient=False, confidence=confidence, evidence_path=evidence)

    def _dismiss_message(self, frame: np.ndarray, boxes: list[TextBox]) -> str | None:
        """Pulsa el botón del mensaje (ACEPTAR…) y espera a VER que el aviso desaparece.

        Devuelve None si se cerró, o el motivo si no (queda en notes y en Message.reason).
        """
        if not self.profile.message_dismiss_texts:
            return None
        button = next((b for t in self.profile.message_dismiss_texts if (b := _find_word(boxes, t))), None)
        height, width = frame.shape[:2]
        if button is not None:
            self._source.click(button.cx / width, button.cy / height)
        elif self.profile.message_dismiss_hint is not None:
            self.notes.append("botón del mensaje no leído por OCR: se pulsó la pista del perfil")
            self._source.click(*center(self.profile.message_dismiss_hint))
        else:
            self.notes.append("mensaje visible: no se encontró su botón para cerrarlo")
            return "mensaje visible: no se encontró su botón para cerrarlo"
        warning = [normalize(t) for texts in self.profile.insufficient_texts.values() for t in texts]
        start = time.monotonic()
        while time.monotonic() - start < self.profile.spin_end.start_timeout_s:
            now = normalize(full_text(read_text(self._source.grab())))
            if not any(w in now for w in warning):
                return None
        self.notes.append("mensaje visible: se pulsó su botón pero no desapareció")
        return "mensaje visible: se pulsó su botón pero no desapareció"

    # ---------- utilidades ----------

    def _wait_for_change(self, reference: np.ndarray, timeout_s: float) -> np.ndarray | None:
        """Primer frame que difiere de `reference`, o None si no cambia nada antes del timeout."""
        threshold = self.profile.spin_end.diff_threshold
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            frame = self._source.grab()
            if change_ratio(reference, frame) > threshold:
                return frame
        return None


def _doubtful(reading: Reading, reason: str) -> Reading:
    """La misma lectura sin importe: lo que se ve no prueba lo que se pidió."""
    return Reading(raw_text=reading.raw_text, evidence_path=reading.evidence_path, reason=reason)


def _above(bet: Reading, balance: Reading | None) -> bool:
    return balance is not None and bet.ok and balance.ok and bet.money.amount > balance.money.amount


@dataclass(frozen=True)
class _Read:
    text: str
    money: Money | None
    score: float


def _reconcile(first: _Read, second: _Read | None) -> tuple[str, Money | None, str | None]:
    """Primera lectura dudosa o ilegible + relectura recortada. Solo se acepta un importe confirmado.

    - Las dos se leen y coinciden: se acepta.
    - Se contradicen: inconclusive (no se elige).
    - Solo la relectura se lee: se acepta si su OCR es fiable (la primera estaba cortada o era ilegible).
    - Si no: inconclusive. Una lectura de baja confianza sin confirmar nunca se devuelve.
    """
    if second is None or second.money is None:
        return first.text, None, f"lectura dudosa sin confirmar '{first.text}' (OCR {first.score:.2f})"
    if first.money is not None and first.money != second.money:
        return first.text, None, f"dos lecturas distintas '{first.text}' y '{second.text}'"
    if first.money is not None or second.score >= _TRUSTED_SCORE:
        return second.text, second.money, None
    return first.text, None, f"relectura poco fiable '{second.text}' (OCR {second.score:.2f})"


def _find_word(boxes: list[TextBox], text: str) -> TextBox | None:
    """Caja cuyo texto es exactamente esa palabra o frase ('OK' no casa con 'BOOK OF DEAD')."""
    wanted = normalize(text)
    return next((b for b in boxes if re.fullmatch(rf"\W*{re.escape(wanted)}\W*", b.norm)), None)


def _find_box(boxes: list[TextBox], text: str) -> TextBox | None:
    wanted = normalize(text)
    return next((b for b in boxes if wanted in b.norm), None)
