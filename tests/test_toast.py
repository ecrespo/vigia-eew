"""Pruebas del toast nativo (RF-14, RNF-03)."""

from __future__ import annotations

from datetime import UTC, datetime

from desktop_notifier import Urgency

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.toast import Toaster


def _ev(severidad="critico", **kw) -> SeismicEvent:
    base = dict(
        id="x",
        fuente="EMSC",
        magnitud=6.1,
        mag_type="mw",
        lugar="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        profundidad_km=12.0,
        hora_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distancia_km=162.0,
        severidad=severidad,
    )
    base.update(kw)
    return SeismicEvent(**base)


class _FakeNotifier:
    def __init__(self, *, falla=False):
        self.enviados: list[dict] = []
        self._falla = falla

    async def send(self, *, title, message, urgency, **kw):
        if self._falla:
            raise RuntimeError("dbus caído")
        self.enviados.append({"title": title, "message": message, "urgency": urgency})


async def test_envia_toast_con_titulo_y_mensaje():
    notifier = _FakeNotifier()
    await Toaster(notifier=notifier, nombre_referencia="Caracas").notificar(_ev())
    assert len(notifier.enviados) == 1
    enviado = notifier.enviados[0]
    assert "6.1" in enviado["title"]
    assert "Caracas" in enviado["message"]


async def test_urgencia_por_severidad():
    async def urgencia_de(sev):
        n = _FakeNotifier()
        await Toaster(notifier=n).notificar(_ev(severidad=sev))
        return n.enviados[0]["urgency"]

    assert await urgencia_de("info") == Urgency.Low
    assert await urgencia_de("atencion") == Urgency.Normal
    assert await urgencia_de("critico") == Urgency.Critical


async def test_fallo_del_notifier_no_propaga():
    notifier = _FakeNotifier(falla=True)
    # No debe lanzar: un fallo del toast no puede tumbar la alerta (RNF-03).
    await Toaster(notifier=notifier).notificar(_ev())
