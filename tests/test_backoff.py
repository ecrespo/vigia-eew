"""Pruebas del backoff exponencial con jitter (RF-03, RNF-03)."""

from __future__ import annotations

import pytest

from vigia_eew.backoff import exponential_backoff


def test_secuencia_sin_jitter():
    # Sin jitter, la espera duplica: 1, 2, 4, 8 s (base=1).
    assert exponential_backoff(1, base=1.0, tope=60.0, jitter=False) == 1.0
    assert exponential_backoff(2, base=1.0, tope=60.0, jitter=False) == 2.0
    assert exponential_backoff(3, base=1.0, tope=60.0, jitter=False) == 4.0
    assert exponential_backoff(4, base=1.0, tope=60.0, jitter=False) == 8.0


def test_se_satura_en_el_tope():
    # base*2^(intento-1) crecería sin límite; se satura en `tope`.
    assert exponential_backoff(7, base=1.0, tope=60.0, jitter=False) == 60.0
    assert exponential_backoff(20, base=1.0, tope=60.0, jitter=False) == 60.0


def test_jitter_acota_entre_mitad_y_total():
    # Equal jitter: resultado en [capped/2, capped]. intento=4 -> capped=8.
    assert exponential_backoff(4, base=1.0, tope=60.0, rng=lambda: 0.0) == 4.0
    assert exponential_backoff(4, base=1.0, tope=60.0, rng=lambda: 1.0) == 8.0
    medio = exponential_backoff(4, base=1.0, tope=60.0, rng=lambda: 0.5)
    assert medio == 6.0


def test_jitter_nunca_supera_el_tope():
    # Incluso con rng=1.0 en intentos altos, no se supera `tope`.
    assert exponential_backoff(30, base=1.0, tope=60.0, rng=lambda: 1.0) == 60.0


def test_intento_invalido():
    with pytest.raises(ValueError):
        exponential_backoff(0)
