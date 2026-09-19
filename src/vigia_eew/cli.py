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
        "--tui",
        action="store_true",
        help="Runs the headless terminal dashboard instead of the desktop GUI (RF-36).",
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


def _check_config(config_path: str | None) -> int:
    """`--check-config`: validate and describe, then exit (RF-25)."""
    cfg = load_config(config_path)
    print(
        f"Config OK - reference={cfg.reference.name} "
        f"({cfg.reference.lat}, {cfg.reference.lon}) - "
        f"radius={cfg.filter.radius_km} km - min_mag={cfg.filter.min_magnitude}"
    )
    return 0


def _manage_autostart(*, install: bool, create_installer: Callable[[], Any] | None) -> int:
    """`--install-autostart` / `--uninstall-autostart` (RF-22, RF-23)."""
    if create_installer is None:
        from vigia_eew.autostart import create_installer as create_installer_real

        create_installer = create_installer_real
    installer = create_installer()
    if install:
        installer.install()
        print("Autostart installed.")
    else:
        installer.uninstall()
        print("Autostart uninstalled.")
    return 0


def _run_agent(args: argparse.Namespace, create_app: Callable[..., Any] | None) -> int:
    """Starts the agent in the mode the flags asked for."""
    if args.config is None:
        # First-run seeding (RF-24): with no explicit --config, create the
        # per-OS config file from the bundled template if it does not exist.
        # Best-effort; an explicit --config path is never auto-created, so it
        # keeps raising FileNotFoundError.
        from vigia_eew.config import seed_config_if_missing

        seed_config_if_missing()

    cfg = load_config(args.config)
    if create_app is None:
        from vigia_eew.app import Application

        create_app = Application
    app = create_app(
        cfg, manual_reference=has_manual_reference(args.config), config_path=args.config
    )

    if args.tui:
        app.run_tui(simulate=args.simulate)
    elif args.simulate:
        app.simulate()
    else:
        app.execute()
    return 0


def main(
    argv: list[str] | None = None,
    *,
    create_app: Callable[..., Any] | None = None,
    create_installer: Callable[[], Any] | None = None,
) -> int:
    """Console entry point. Returns a standard exit code.

    Three of the flags are whole modes that exit on their own rather than
    starting the agent, so each is its own function. What is left here is the
    dispatch, which is the only thing `main` should be about.
    """
    args = _build_parser().parse_args(argv)

    if args.check_config:
        return _check_config(args.config)
    if args.install_autostart or args.uninstall_autostart:
        return _manage_autostart(install=args.install_autostart, create_installer=create_installer)
    return _run_agent(args, create_app)


if __name__ == "__main__":
    raise SystemExit(main())
