"""Punto de entrada de consola `vigia-eew` (RF-26).

NOTA: Este módulo es un *stub* de la Fase 1. La CLI completa (arranque del agente,
`--simulate`, instalación de autoarranque) se implementa en la Fase 5
(ver `docs/IMPLEMENTATION-PLAN.md`). Por ahora solo expone versión y carga de config
para verificar que el empaquetado y el entry point funcionan.
"""

from __future__ import annotations

import argparse

from . import __version__
from .config import cargar_config


def main(argv: list[str] | None = None) -> int:
    """Entrada de consola. Devuelve un código de salida estándar."""
    parser = argparse.ArgumentParser(
        prog="vigia-eew",
        description="Agente de alerta sísmica en tiempo real (EMSC push + USGS respaldo).",
    )
    parser.add_argument("--version", action="version", version=f"vigia-eew {__version__}")
    parser.add_argument("--config", metavar="RUTA", help="Ruta a un config.toml.")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Carga y valida la configuración, e imprime el punto de referencia.",
    )
    args = parser.parse_args(argv)

    if args.check_config:
        cfg = cargar_config(args.config)
        print(
            f"Config OK · referencia={cfg.referencia.nombre} "
            f"({cfg.referencia.lat}, {cfg.referencia.lon}) · "
            f"radio={cfg.filtro.radio_km} km · mag_min={cfg.filtro.magnitud_minima}"
        )
        return 0

    print("vigia-eew: la ejecución del agente se habilita en la Fase 5. Usa --help.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
