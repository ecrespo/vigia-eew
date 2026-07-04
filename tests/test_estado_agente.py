"""Pruebas del estado compartido para el ícono de bandeja (RF-34)."""

from __future__ import annotations

from vigia_eew.estado_agente import EstadoAgente


def test_defaults():
    e = EstadoAgente()
    assert e.ws_conectado is False
    assert e.ultima_alerta is None


def test_marcar_conectado_y_reconectando():
    e = EstadoAgente()
    e.marcar_conectado()
    assert e.ws_conectado is True
    e.marcar_reconectando()
    assert e.ws_conectado is False


def test_marcar_ultima_alerta():
    e = EstadoAgente()
    e.marcar_ultima_alerta("M 6.1 · cerca de La Guaira · 2026-06-28 13:39:00")
    assert e.ultima_alerta == "M 6.1 · cerca de La Guaira · 2026-06-28 13:39:00"
