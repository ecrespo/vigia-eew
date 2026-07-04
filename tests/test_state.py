"""Pruebas de persistencia de estado (RF-06, RF-10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigia_eew.config import Referencia
from vigia_eew.models import AlertedId, EventSignature
from vigia_eew.state import StateStore


def _store(tmp_path) -> StateStore:
    return StateStore(tmp_path / "state.json")


def test_carga_inicial_vacia(tmp_path):
    s = _store(tmp_path)
    estado = s.cargar()
    assert estado.ids_alertados == []
    assert estado.cursor_usgs_ms is None


def test_persistencia_ida_y_vuelta(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.registrar_alertado(
        AlertedId(id="us6000t8sx", fuente="USGS", hora_utc=datetime.now(UTC))
    )
    s.actualizar_cursor_usgs(1782639238852)
    s.guardar()

    # Nueva instancia que relee desde disco (simula reinicio, RF-10).
    s2 = _store(tmp_path)
    s2.cargar()
    assert s2.ya_alertado("us6000t8sx")
    assert s2.estado.cursor_usgs_ms == 1782639238852


def test_no_realertar_tras_reinicio(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.registrar_alertado(
        AlertedId(id="abc", fuente="EMSC", hora_utc=datetime.now(UTC))
    )
    s.guardar()
    s2 = _store(tmp_path)
    s2.cargar()
    assert s2.ya_alertado("abc") is True
    assert s2.ya_alertado("otro") is False


def test_cursor_solo_avanza(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.actualizar_cursor_usgs(100)
    s.actualizar_cursor_usgs(50)  # menor: no debe retroceder
    assert s.estado.cursor_usgs_ms == 100
    s.actualizar_cursor_usgs(200)
    assert s.estado.cursor_usgs_ms == 200


def test_marcar_reconocido(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.registrar_alertado(
        AlertedId(id="abc", fuente="EMSC", hora_utc=datetime.now(UTC))
    )
    s.marcar_reconocido("abc")
    assert s.estado.ids_alertados[0].reconocido_utc is not None


def test_poda_por_antiguedad(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    ahora = datetime.now(UTC)
    viejo = ahora - timedelta(hours=48)
    s.registrar_alertado(AlertedId(id="viejo", fuente="USGS", hora_utc=viejo))
    s.registrar_alertado(AlertedId(id="nuevo", fuente="USGS", hora_utc=ahora))
    s.agregar_firma(EventSignature(lat=10, lon=-66, hora_utc=viejo, magnitud=4.0))
    s.podar(ahora=ahora)
    ids = {a.id for a in s.estado.ids_alertados}
    assert ids == {"nuevo"}
    assert s.estado.firmas_recientes == []


def test_estado_corrupto_no_rompe(tmp_path):
    ruta = tmp_path / "state.json"
    ruta.write_text("{ esto no es json valido ", encoding="utf-8")
    s = StateStore(ruta)
    estado = s.cargar()  # no debe lanzar; parte de cero
    assert estado.ids_alertados == []


def test_escritura_atomica_deja_archivo_unico(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.guardar()
    archivos = list(tmp_path.iterdir())
    # Solo debe quedar state.json, sin temporales .tmp colgando.
    assert [p.name for p in archivos] == ["state.json"]


def test_ubicacion_cacheada_vacia_por_defecto(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    assert s.ubicacion_cacheada() is None


def test_cachear_y_recuperar_ubicacion(tmp_path):
    s = _store(tmp_path)
    s.cargar()
    s.cachear_ubicacion(Referencia(nombre="Maracaibo", lat=10.63, lon=-71.64))
    s.guardar()

    s2 = _store(tmp_path)
    s2.cargar()
    cacheada = s2.ubicacion_cacheada()
    assert cacheada is not None
    assert cacheada.nombre == "Maracaibo"
    assert cacheada.lat == 10.63
    assert cacheada.lon == -71.64
