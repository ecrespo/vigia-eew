"""Console entry point `vigia-eew` (RF-26, RF-21).

Starts the full agent (`vigia-eew`) or the notification test (`--simulate`),
accepts a config path (`--config`) and a quick check (`--check-config`).
Autostart install/uninstall was added in Phase 6.

The application factory (`create_app`) is injectable so the CLI dispatch can be
tested without starting the GUI or the network.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from vigia_eew import __version__
from vigia_eew.config import has_manual_reference, load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vigia-eew",
        description="Real-time seismic alert agent (EMSC push + USGS backup).",
    )
    parser.add_argument("--version", action="version", version=f"vigia-eew {__version__}")
    parser.add_argument("--config", metavar="PATH", help="Path to a config.toml.")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Loads and validates the configuration, and prints the reference point.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Injects a simulated earthquake (M6.1 La Guaira) to test the alert (RF-21).",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Installs autostart on login (RF-22, RF-23) and exits.",
    )
    parser.add_argument(
        "--uninstall-autostart",
        action="store_true",
        help="Uninstalls autostart (RF-23) and exits.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    create_app: Callable[..., Any] | None = None,
    create_installer: Callable[[], Any] | None = None,
) -> int:
    """Console entry point. Returns a standard exit code."""
    args = _build_parser().parse_args(argv)

    if args.check_config:
        cfg = load_config(args.config)
        print(
            f"Config OK - reference={cfg.reference.name} "
            f"({cfg.reference.lat}, {cfg.reference.lon}) - "
            f"radius={cfg.filter.radius_km} km - min_mag={cfg.filter.min_magnitude}"
        )
        return 0

    if args.install_autostart or args.uninstall_autostart:
        if create_installer is None:
            from vigia_eew.autostart import create_installer as create_installer_real

            create_installer = create_installer_real
        installer = create_installer()
        if args.install_autostart:
            installer.install()
            print("Autostart installed.")
        else:
            installer.uninstall()
            print("Autostart uninstalled.")
        return 0

    cfg = load_config(args.config)
    if create_app is None:
        from vigia_eew.app import Application

        create_app = Application
    app = create_app(
        cfg, manual_reference=has_manual_reference(args.config), config_path=args.config
    )

    if args.simulate:
        app.simulate()
    else:
        app.execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
