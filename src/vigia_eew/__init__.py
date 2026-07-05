"""Vigía-eew — real-time earthquake alert agent, impossible to ignore.

Main package. Exposes the version and the core data models.
See `docs/` for the Spec-Driven Development artifacts.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the installed distribution's version (set from
    # pyproject.toml at build time), so `--version` never drifts from the release.
    __version__ = version("vigia-eew")
except PackageNotFoundError:  # not installed (e.g. running from a bare checkout)
    __version__ = "0.0.0"

__all__ = ["__version__"]
