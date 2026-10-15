"""Alias corto: `python -m betsson.run` = `python -m betsson.site.run` (ver docs/demo/UN-COMANDO.md)."""
from betsson.site.run import main

if __name__ == "__main__":
    raise SystemExit(main())
