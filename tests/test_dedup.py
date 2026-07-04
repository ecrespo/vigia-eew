"""Pruebas de la deduplicación (RF-09, RF-10, RF-11; heurística en TECHNICAL-DESIGN §5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigia_eew.config import Dedup
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.state import StateStore

_BASE = datetime(2026, 6, 28, 13, 39, tzinfo=UTC)


def _ev(
    *,
    id="evt-1",
    fuente="EMSC",
    accion="create",
    lat=10.5,
    lon=-66.9,
    mag=6.0,
    hora=_BASE,
) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        fuente=fuente,
        magnitud=mag,
        mag_type="mw",
        lat=lat,
        lon=lon,
        profundidad_km=10.0,
        hora_utc=hora,
        distancia_km=20.0,
        severidad="critico",
        accion=accion,
    )


def _dedup(tmp_path, **cfg):
    estado = StateStore(tmp_path / "state.json")
    estado.cargar()
    return Deduplicator(Dedup(**cfg), estado), estado


# --- Dedup por id (RF-10, RF-11) ---


def test_evento_nuevo(tmp_path):
    dedup, _ = _dedup(tmp_path)
    assert dedup.clasificar(_ev()) == "nuevo"


def test_mismo_id_create_es_duplicado(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="abc"))
    assert dedup.clasificar(_ev(id="abc")) == "duplicado"


def test_mismo_id_update_es_actualizar(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="abc"))
    assert dedup.clasificar(_ev(id="abc", accion="update")) == "actualizar"


def test_update_de_id_no_alertado_es_nuevo(tmp_path):
    # Un "update" cuyo create nunca se alertó (p. ej. filtrado) se evalúa como nuevo.
    dedup, _ = _dedup(tmp_path)
    assert dedup.clasificar(_ev(id="nunca-visto", accion="update")) == "nuevo"


# --- Heurística inter-fuente (RF-09) ---


def test_inter_fuente_duplicado(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="emsc-1", fuente="EMSC", lat=10.50, lon=-66.90, mag=6.0))
    # USGS: otro id, cerca (<100 km), <90 s, <0.5 mag -> mismo sismo.
    usgs = _ev(
        id="usgs-1", fuente="USGS", lat=10.55, lon=-66.93, mag=6.2,
        hora=_BASE + timedelta(seconds=30),
    )
    assert dedup.clasificar(usgs) == "duplicado"


def test_inter_fuente_lejos_es_nuevo(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0))
    lejos = _ev(id="usgs-1", fuente="USGS", lat=13.0, lon=-69.0, mag=6.0)
    assert dedup.clasificar(lejos) == "nuevo"


def test_inter_fuente_fuera_de_ventana_es_nuevo(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0, hora=_BASE))
    tarde = _ev(
        id="usgs-1", fuente="USGS", lat=10.5, lon=-66.9, mag=6.0,
        hora=_BASE + timedelta(seconds=200),
    )
    assert dedup.clasificar(tarde) == "nuevo"


def test_inter_fuente_magnitud_distinta_es_nuevo(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0))
    otra_mag = _ev(id="usgs-1", fuente="USGS", lat=10.5, lon=-66.9, mag=7.0)
    assert dedup.clasificar(otra_mag) == "nuevo"


# --- Persistencia (RF-10) ---


def test_registrar_persiste_id_y_firma(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="abc"))

    recargado = StateStore(tmp_path / "state.json")
    recargado.cargar()
    assert recargado.ya_alertado("abc")
    assert len(recargado.estado.firmas_recientes) == 1


def test_sobrevive_reinicio(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.registrar(_ev(id="abc"))

    # Nuevo Deduplicator sobre estado releído (simula reinicio, RF-10).
    estado2 = StateStore(tmp_path / "state.json")
    estado2.cargar()
    dedup2 = Deduplicator(Dedup(), estado2)
    assert dedup2.clasificar(_ev(id="abc")) == "duplicado"
