"""Punto de entrada de consola `vigia-eew` (RF-26, RF-21).

Arranca el agente completo (`vigia-eew`) o la prueba de notificación (`--simulate`),
admite una ruta de config (`--config`) y una verificación rápida (`--check-config`).
La instalación/desinstalación de autoarranque se añade en la Fase 6.

La factoría de la aplicación (`crear_app`) es inyectable para poder probar el despacho
de la CLI sin arrancar la GUI ni la red.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from . import __version__
from .config import cargar_config, tiene_referencia_manual


def _construir_parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Inyecta un sismo simulado (M6.1 La Guaira) para probar la alerta (RF-21).",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Instala el autoarranque al iniciar sesión (RF-22, RF-23) y sale.",
    )
    parser.add_argument(
        "--uninstall-autostart",
        action="store_true",
        help="Desinstala el autoarranque (RF-23) y sale.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    crear_app: Callable[..., Any] | None = None,
    crear_instalador: Callable[[], Any] | None = None,
) -> int:
    """Entrada de consola. Devuelve un código de salida estándar."""
    args = _construir_parser().parse_args(argv)

    if args.check_config:
        cfg = cargar_config(args.config)
        print(
            f"Config OK · referencia={cfg.referencia.nombre} "
            f"({cfg.referencia.lat}, {cfg.referencia.lon}) · "
            f"radio={cfg.filtro.radio_km} km · mag_min={cfg.filtro.magnitud_minima}"
        )
        return 0

    if args.install_autostart or args.uninstall_autostart:
        if crear_instalador is None:
            from .autostart import crear_instalador as crear_instalador_real

            crear_instalador = crear_instalador_real
        instalador = crear_instalador()
        if args.install_autostart:
            instalador.instalar()
            print("Autoarranque instalado.")
        else:
            instalador.desinstalar()
            print("Autoarranque desinstalado.")
        return 0

    cfg = cargar_config(args.config)
    if crear_app is None:
        from .app import Aplicacion

        crear_app = Aplicacion
    app = crear_app(cfg, referencia_manual=tiene_referencia_manual(args.config))

    if args.simulate:
        app.simular()
    else:
        app.ejecutar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
