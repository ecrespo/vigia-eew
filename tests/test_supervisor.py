"""Pruebas del orquestador asyncio (RNF-03, RNF-04)."""

from __future__ import annotations

import asyncio

from vigia_eew.supervisor import Supervisor


async def test_arranca_cada_tarea_registrada():
    corrieron: set[str] = set()
    esperas: list[float] = []

    async def sleep(s):
        esperas.append(s)

    sup = Supervisor(sleep=sleep, jitter=False, manejar_senales=False)

    async def hacer(nombre):
        corrieron.add(nombre)
        sup.solicitar_parada()  # una tarea pide parar; el resto se cancela limpio

    sup.add("a", lambda: hacer("a"))
    sup.add("b", lambda: hacer("b"))

    await asyncio.wait_for(sup.run(), timeout=1.0)
    assert "a" in corrieron  # al menos la primera corrió y disparó la parada


async def test_reinicia_tarea_que_falla_con_backoff():
    esperas: list[float] = []

    async def sleep(s):
        esperas.append(s)

    sup = Supervisor(sleep=sleep, jitter=False, manejar_senales=False)
    llamadas: list[int] = []

    async def falla():
        llamadas.append(1)
        if len(llamadas) >= 3:
            sup.solicitar_parada()
            return
        raise RuntimeError("boom")

    sup.add("falla", falla)
    await asyncio.wait_for(sup.run(), timeout=1.0)

    assert len(llamadas) == 3  # reinició tras cada fallo
    assert esperas == [1.0, 2.0]  # backoff exponencial entre reintentos


async def test_aisla_fallos_entre_tareas():
    async def sleep(s):
        return None

    sup = Supervisor(sleep=sleep, jitter=False, manejar_senales=False)
    buena_corrio = asyncio.Event()
    intentos_mala = 0

    async def buena():
        buena_corrio.set()
        await asyncio.sleep(3600)  # vive hasta que la cancelen

    async def mala():
        nonlocal intentos_mala
        intentos_mala += 1
        if intentos_mala >= 3:
            sup.solicitar_parada()
            return
        raise RuntimeError("boom")

    sup.add("buena", buena)
    sup.add("mala", mala)
    await asyncio.wait_for(sup.run(), timeout=1.0)

    assert buena_corrio.is_set()  # el fallo de "mala" no impidió "buena"
    assert intentos_mala == 3


async def test_parada_limpia_cancela_tareas_vivas():
    async def sleep(s):
        return None

    sup = Supervisor(sleep=sleep, manejar_senales=False)
    arranco = asyncio.Event()
    cancelada = asyncio.Event()

    async def larga():
        arranco.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelada.set()
            raise

    sup.add("larga", larga)
    run_task = asyncio.create_task(sup.run())
    await asyncio.wait_for(arranco.wait(), timeout=1.0)
    sup.solicitar_parada()
    await asyncio.wait_for(run_task, timeout=1.0)

    assert cancelada.is_set()  # cierre limpio: la tarea viva fue cancelada (RNF-04)
