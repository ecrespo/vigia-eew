"""Shared test fixtures.

Isolate the whole suite from the real user config directory: tests must never
read the developer's `~/.config/vigia-eew/config.toml` nor seed one there
(RF-24). Each test gets a unique, non-existent default path under `tmp_path`.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch, tmp_path):
    from vigia_eew import config as config_module

    monkeypatch.setattr(
        config_module,
        "default_config_path",
        lambda: tmp_path / "vigia-eew" / "config.toml",
    )
