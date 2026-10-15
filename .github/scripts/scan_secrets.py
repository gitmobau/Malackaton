"""Falla si algún valor secreto aparece en las evidencias (también dentro de los .zip de traza).

Busca el valor tal cual y codificado (URL, JSON y base64), que es como lo guarda la traza.
Lee los valores de las variables BETSSON_* y ANTHROPIC_API_KEY del entorno y nunca los imprime.
Nombre del titular (BETSSON_[<MERCADO>_][EMPTY_]HOLDER_NAME): además se busca, sin distinguir mayúsculas
ni tildes, en el texto de los archivos y con OCR en las capturas (en una imagen son píxeles, no bytes).
Falla cerrado: sin credenciales en el entorno o con un archivo ilegible, devuelve error.
Uso: python scan_secrets.py <carpeta> [--require-holder]
  --require-holder: falla si no hay ningún BETSSON_*_HOLDER_NAME en el entorno (CI).
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, quote_plus

SECRET_PREFIXES = ("BETSSON_", "ANTHROPIC_API_KEY")
# Credenciales obligatorias: genéricas (CI) o por mercado (.env local), p. ej. BETSSON_ES_USERNAME.
REQUIRED = re.compile(r"^BETSSON_(?:[A-Z]+_)?(USERNAME|PASSWORD)$")
HOLDER = re.compile(r"^BETSSON_(?:[A-Z]+_)*HOLDER_NAME$")  # también ..._EMPTY_HOLDER_NAME (cuenta de S2)
MIN_LEN = 4  # evitar falsos positivos con valores triviales
MIN_WORD = 3  # cada palabra del nombre (nombre de pila, apellidos) se busca suelta
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
OCR_UPSCALE = 2  # la cabecera de Betsson usa letra pequeña


def missing_credentials() -> list[str]:
    present = {m.group(1) for k, v in os.environ.items() if v and (m := REQUIRED.match(k))}
    return [f"BETSSON_[<MERCADO>_]{kind}" for kind in ("USERNAME", "PASSWORD") if kind not in present]


def variants(value: str) -> set[bytes]:
    forms = {value, quote(value, safe=""), quote_plus(value), json.dumps(value)[1:-1]}
    return {f.encode() for f in forms} | {base64.b64encode(value.encode())}


def secret_needles() -> set[bytes]:
    needles: set[bytes] = set()
    for key, value in os.environ.items():
        if key.startswith(SECRET_PREFIXES) and value and len(value) >= MIN_LEN:
            needles |= variants(value)
    return needles


def blobs(path: Path) -> Iterator[tuple[str, bytes]]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                yield f"{path}!{name}", zf.read(name)
    else:
        yield str(path), path.read_bytes()


def normalize(text: str) -> str:
    """Minúsculas, sin tildes y con los separadores reducidos a un espacio."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def holder_words() -> set[str]:
    """Cada palabra de cada nombre de titular (la web puede mostrar solo el nombre de pila)."""
    words: set[str] = set()
    for key, value in os.environ.items():
        if HOLDER.match(key) and value:
            words |= {w for w in normalize(value).split() if len(w) >= MIN_WORD}
    return words


def mentions(text: str, words: set[str]) -> bool:
    padded = f" {normalize(text)} "
    return any(f" {w} " in padded for w in words)


@lru_cache(maxsize=1)
def _ocr_engine():  # noqa: ANN202 - tipo de un paquete externo
    try:  # rapidocr v3 (Python 3.14)
        from rapidocr import RapidOCR
    except ImportError:  # rapidocr-onnxruntime v1
        from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def image_text(path: Path) -> str:
    import cv2
    import numpy as np

    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise OSError("imagen ilegible")
    image = cv2.resize(image, None, fx=OCR_UPSCALE, fy=OCR_UPSCALE, interpolation=cv2.INTER_CUBIC)
    output = _ocr_engine()(image)
    if isinstance(output, tuple):  # v1: (resultados, tiempos)
        return " ".join(r[1] for r in (output[0] or []))
    return " ".join(getattr(output, "txts", None) or ())


def holder_leak(path: Path, data: bytes, words: set[str]) -> bool:
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return mentions(image_text(path), words)
    text = data.decode("utf-8", "ignore")
    # results.json guarda "Í" como Í: se desescapa antes de comparar.
    unescaped = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return mentions(unescaped, words)


def scan(root: Path, needles: set[bytes], words: set[str] = frozenset()) -> list[str]:
    leaks: list[str] = []
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        try:
            leaks += [where for where, data in blobs(file) if any(n in data for n in needles)]
            if words and holder_leak(file, file.read_bytes(), words):
                leaks.append(f"{file} (nombre del titular)")
        except (zipfile.BadZipFile, OSError, ImportError):
            leaks.append(f"{file} (ilegible: se trata como fuga)")
    return leaks


def main(root: str, require_holder: bool = False) -> int:
    missing = missing_credentials()
    if missing:
        print(f"Faltan credenciales en el entorno ({', '.join(missing)}): no se puede escanear.")
        return 2
    words = holder_words()
    if require_holder and not words:
        print("Falta BETSSON_[<MERCADO>_]HOLDER_NAME en el entorno: no se puede comprobar el nombre del titular.")
        return 2
    path = Path(root)
    if not path.exists():
        print(f"No existe {root}: nada que publicar.")
        return 0
    leaks = scan(path, secret_needles(), words)
    for where in leaks:
        print(f"FUGA DE SECRETO en: {where}")
    print(f"Revisado {root}: {len(leaks)} fugas.")
    return 1 if leaks else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0] if args else "outputs", require_holder="--require-holder" in sys.argv))
