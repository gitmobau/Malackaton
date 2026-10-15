"""Falla si algún valor secreto aparece en las evidencias (también dentro de los .zip de traza).

Busca el valor tal cual y codificado (URL, JSON y base64), que es como lo guarda la traza.
Lee los valores de las variables BETSSON_* y ANTHROPIC_API_KEY del entorno y nunca los imprime.
Falla cerrado: sin credenciales en el entorno o con un archivo ilegible, devuelve error.
Uso: python scan_secrets.py <carpeta>
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote, quote_plus

SECRET_PREFIXES = ("BETSSON_", "ANTHROPIC_API_KEY")
# Credenciales obligatorias: genéricas (CI) o por mercado (.env local), p. ej. BETSSON_ES_USERNAME.
REQUIRED = re.compile(r"^BETSSON_(?:[A-Z]+_)?(USERNAME|PASSWORD)$")
MIN_LEN = 4  # evitar falsos positivos con valores triviales


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


def scan(root: Path, needles: set[bytes]) -> list[str]:
    leaks: list[str] = []
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        try:
            leaks += [where for where, data in blobs(file) if any(n in data for n in needles)]
        except (zipfile.BadZipFile, OSError):
            leaks.append(f"{file} (ilegible: se trata como fuga)")
    return leaks


def main(root: str) -> int:
    missing = missing_credentials()
    if missing:
        print(f"Faltan credenciales en el entorno ({', '.join(missing)}): no se puede escanear.")
        return 2
    path = Path(root)
    if not path.exists():
        print(f"No existe {root}: nada que publicar.")
        return 0
    leaks = scan(path, secret_needles())
    for where in leaks:
        print(f"FUGA DE SECRETO en: {where}")
    print(f"Revisado {root}: {len(leaks)} fugas.")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "outputs"))
