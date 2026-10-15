"""GameEyes: mira el canvas del juego como un jugador. No conoce ningún proveedor: todo sale del perfil.

Reglas:
- La prueba es lo visible (OCR, plantillas, cambio de imagen). Un clic nunca es prueba.
- Lo dudoso devuelve money=None / completed=False con reason="inconclusive: …". Nunca un valor inventado.
- Si el perfil no reconoce el juego se lanza ProviderUIChanged (no es un FAIL de integración).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from betsson.game.contracts import Message, Money, ProviderUIChanged, Reading, SpinEnd
from betsson.game.sources import FrameSource
from betsson.profiles.base import AmountField, IntroScreen, ProviderProfile
from betsson.vision.anchors import find_amount
from betsson.vision.diff import change_ratio
from betsson.vision.ocr import TextBox, full_text, normalize, read_text
from betsson.vision.template import find_template

MoneyParser = Callable[[str], Money | None]

# Si el OCR a tamaño real no encuentra una etiqueta, se reintenta ampliando (textos pequeños del canvas).
_UPSCALES: tuple[float, ...] = (1.0, 2.0)
_MAX_INTRO_STEPS = 6
_LOADING_TIMEOUT_S = 60.0


class GameEyes:
    def __init__(
        self,
        source: FrameSource,
        profile: ProviderProfile,
        lang: str,
        parse_money: MoneyParser,
        evidence_dir: Path | None = None,
    ) -> None:
        self._source = source
        self._profile = profile
        self._lang = lang
        self._parse_money = parse_money
        self._evidence_dir = evidence_dir
        self.notes: list[str] = []  # qué tuvo que recalibrar o suponer: va al informe

    @property
    def profile(self) -> ProviderProfile:
        return self._profile

    # ---------- evidencias ----------

    def screenshot(self, name: str, frame: np.ndarray | None = None) -> Path | None:
        """Guarda el frame actual (o el dado) como evidencia. Sin evidence_dir no guarda nada."""
        if self._evidence_dir is None:
            return None
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self._evidence_dir / f"{name}.png"
        cv2.imwrite(str(path), self._source.grab() if frame is None else frame)
        return path

    # ---------- importes ----------

    def read_balance(self, frame: np.ndarray | None = None) -> Reading:
        return self.read_amount("balance", frame)

    def read_bet(self, frame: np.ndarray | None = None) -> Reading:
        return self.read_amount("bet", frame)

    def read_win(self, frame: np.ndarray | None = None) -> Reading:
        """La ganancia puede no mostrarse si es 0: entonces es inconclusive y lo decide la regla del saldo."""
        return self.read_amount("win", frame)

    def read_amount(self, field: AmountField, frame: np.ndarray | None = None) -> Reading:
        frame = self._source.grab() if frame is None else frame
        aliases = self._profile.label_aliases(field, self._lang)
        hint_rect = self._profile.hint_zones.get(field)
        height, width = frame.shape[:2]
        hint = hint_rect.to_pixels(width, height) if hint_rect else None
        anchored = None
        for upscale in _UPSCALES:
            anchored = find_amount(read_text(frame, upscale=upscale), aliases, hint)
            if anchored is not None:
                break
        evidence = self.screenshot(f"read_{field}", frame)
        if anchored is None:
            return Reading(
                raw_text="",
                money=None,
                confidence=0.0,
                evidence_path=evidence,
                reason=f"inconclusive: no se ve la etiqueta de {field} ({', '.join(aliases[:4])})",
            )
        money = self._parse_money(anchored.value_text)
        reason = None if money is not None else f"inconclusive: importe ilegible '{anchored.value_text}'"
        return Reading(
            raw_text=anchored.value_text,
            money=money,
            confidence=anchored.confidence if money is not None else 0.0,
            evidence_path=evidence,
            reason=reason,
        )

    # ---------- reconocimiento e inicio ----------

    def ensure_recognized(self, frame: np.ndarray | None = None) -> None:
        """El juego se reconoce si se ven las etiquetas de saldo y apuesta. Si no, ProviderUIChanged."""
        frame = self._source.grab() if frame is None else frame
        missing = [f for f in ("balance", "bet") if self.read_amount(f, frame).raw_text == ""]
        if missing:
            path = self.screenshot("provider_ui_changed", frame)
            raise ProviderUIChanged(
                f"el perfil '{self._profile.name}' no encuentra {missing} en pantalla (evidencia: {path})"
            )

    def dismiss_intro(self) -> list[str]:
        """Cierra las pantallas de inicio que reconozca. Devuelve las que cerró, en orden."""
        dismissed: list[str] = []
        for _ in range(_MAX_INTRO_STEPS):
            frame = self._source.grab()
            boxes = read_text(frame)
            text = normalize(full_text(boxes))
            screen = next(
                (s for s in self._profile.intro_screens if any(normalize(t) in text for t in s.match_texts)),
                None,
            )
            if screen is None:
                break
            if screen.wait_only:
                self._wait_for_change(frame, _LOADING_TIMEOUT_S)
            else:
                target = self._intro_target(screen, frame, boxes)
                if target is None:
                    self.notes.append(f"inconclusive: intro '{screen.name}' sin botón localizable")
                    break
                self._source.click(*target)
                self._wait_for_change(frame, self._profile.spin_end.start_timeout_s)
            dismissed.append(screen.name)
        return dismissed

    def _intro_target(self, screen: IntroScreen, frame: np.ndarray, boxes: list[TextBox]) -> tuple[float, float] | None:
        """Botón para cerrar la intro: por texto, por plantilla y, en último caso, por la pista."""
        height, width = frame.shape[:2]
        if screen.click_text:
            box = _find_box(boxes, screen.click_text)
            if box is not None:
                return (box.cx / width, box.cy / height)
        if screen.click_template:
            match = find_template(frame, [screen.click_template])
            if match is not None:
                return match.center
        if screen.click:
            self.notes.append(f"intro '{screen.name}': botón no encontrado, se usó la pista")
            return screen.click.center
        return None

    # ---------- tirada ----------

    def locate_spin(self, frame: np.ndarray | None = None) -> tuple[float, float] | None:
        """Centro del botón de girar en fracción: plantilla multiescala y, si no, la pista del perfil."""
        frame = self._source.grab() if frame is None else frame
        if self._profile.spin_templates:
            match = find_template(frame, self._profile.spin_templates)
            if match is not None:
                return match.center
            self.notes.append("botón de girar no encontrado por plantilla")
        if self._profile.spin_hint is not None:
            self.notes.append("botón de girar: se usa la pista de zona del perfil")
            return self._profile.spin_hint.center
        return None

    def spin(self) -> bool:
        """Pulsa girar y devuelve True solo si se VE que la tirada empieza (cambio de imagen)."""
        before = self._source.grab()
        self.screenshot("spin_before", before)
        target = self.locate_spin(before)
        if target is not None:
            self._source.click(*target)
        elif self._profile.spin_key:
            self._source.press(self._profile.spin_key)
            self.notes.append(f"girar con la tecla '{self._profile.spin_key}'")
        else:
            self.notes.append("inconclusive: no hay forma de pulsar girar")
            return False
        started = self._wait_for_change(before, self._profile.spin_end.start_timeout_s)
        if started is not None:
            self.screenshot("spin_started", started)
        return started is not None

    def wait_spin_end(self) -> SpinEnd:
        """Fin de tirada = `stable_frames` frames seguidos sin cambio apreciable."""
        signal = self._profile.spin_end
        start = time.monotonic()
        previous = self._source.grab()
        stable = 0
        while time.monotonic() - start < signal.timeout_s:
            current = self._source.grab()
            stable = stable + 1 if change_ratio(previous, current) <= signal.diff_threshold else 0
            previous = current
            if stable >= signal.stable_frames:
                self.screenshot("spin_end", current)
                return SpinEnd(completed=True, duration_s=round(time.monotonic() - start, 2))
        self.screenshot("spin_timeout", previous)
        return SpinEnd(
            completed=False,
            duration_s=round(time.monotonic() - start, 2),
            reason=f"inconclusive: la imagen no se estabilizó en {signal.timeout_s}s",
        )

    # ---------- mensajes ----------

    def read_message(self, frame: np.ndarray | None = None) -> Message:
        """Texto visible y si coincide con el aviso de saldo insuficiente de algún idioma del perfil."""
        frame = self._source.grab() if frame is None else frame
        self.screenshot("message", frame)
        text = full_text(read_text(frame))
        norm = normalize(text)
        langs = [self._lang] + [l for l in self._profile.insufficient_texts if l != self._lang]
        for lang in langs:
            if any(normalize(t) in norm for t in self._profile.insufficient_texts.get(lang, [])):
                return Message(text=text, lang_detected=lang, matches_insufficient=True)
        return Message(text=text, lang_detected=None, matches_insufficient=False)

    # ---------- utilidades ----------

    def _wait_for_change(self, reference: np.ndarray, timeout_s: float) -> np.ndarray | None:
        """Primer frame que difiere de `reference`, o None si no cambia nada antes del timeout."""
        threshold = self._profile.spin_end.diff_threshold
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            frame = self._source.grab()
            if change_ratio(reference, frame) > threshold:
                return frame
        return None


def _find_box(boxes: list[TextBox], text: str) -> TextBox | None:
    wanted = normalize(text)
    return next((b for b in boxes if wanted in b.norm), None)
