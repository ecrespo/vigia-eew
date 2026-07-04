"""Tests for the i18n module (RF-35)."""

from __future__ import annotations

from vigia_eew.i18n import detect_os_locale, resolve_locale, t


def test_t_returns_english_by_default():
    assert t("acknowledged_button") == "ACKNOWLEDGED"


def test_t_returns_spanish_when_requested():
    assert t("acknowledged_button", "es") == "RECONOCIDO"


def test_t_falls_back_to_english_for_unsupported_locale():
    assert t("acknowledged_button", "fr") == "ACKNOWLEDGED"


def test_t_formats_placeholders():
    assert t("toast_title", "en", magnitude="M 6.1") == "Seismic alert M 6.1"
    assert t("toast_title", "es", magnitude="M 6.1") == "Alerta sísmica M 6.1"


def test_t_unknown_key_returns_the_key_itself():
    assert t("no_such_key") == "no_such_key"


def test_resolve_locale_explicit_supported():
    assert resolve_locale("es") == "es"
    assert resolve_locale("en") == "en"


def test_resolve_locale_explicit_unsupported_falls_back_to_english():
    assert resolve_locale("fr") == "en"


def test_resolve_locale_auto_uses_detected_locale(monkeypatch):
    monkeypatch.setenv("LC_ALL", "es_VE.UTF-8")
    assert resolve_locale("auto") == "es"


def test_resolve_locale_auto_unsupported_detected_falls_back(monkeypatch):
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    assert resolve_locale("auto") == "en"


def test_detect_os_locale_reads_lc_all_first(monkeypatch):
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert detect_os_locale() == "es"


def test_detect_os_locale_falls_back_to_default_without_env(monkeypatch):
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.setattr("vigia_eew.i18n.locale.getlocale", lambda: (None, None))
    assert detect_os_locale() == "en"
