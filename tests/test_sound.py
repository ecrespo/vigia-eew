"""Pruebas de la capa de audio (RF-17, RNF-03)."""

from __future__ import annotations

from pathlib import Path

from vigia_eew.notify.sound import (
    PERFILES,
    SoundPlayer,
    comando_reproductor,
)


class _Reproductor:
    """Reproductor falso que registra las rutas reproducidas."""

    def __init__(self, *, falla=False):
        self.rutas: list[Path] = []
        self._falla = falla

    def __call__(self, ruta: Path) -> None:
        self.rutas.append(ruta)
        if self._falla:
            raise RuntimeError("audio no disponible")


def _player(reproductor, *, habilitado=True, assets_dir=Path("/assets"), sleep=None):
    return SoundPlayer(
        reproductor=reproductor,
        sleep=sleep or (lambda _s: None),
        habilitado=habilitado,
        assets_dir=assets_dir,
    )


# --- Perfil por severidad (RF-17: más insistente cuanto más grave) ---


def test_insistencia_crece_con_severidad():
    assert PERFILES["info"].repeticiones < PERFILES["atencion"].repeticiones
    assert PERFILES["atencion"].repeticiones < PERFILES["critico"].repeticiones


def test_reproduce_segun_repeticiones_critico():
    rep = _Reproductor()
    _player(rep).reproducir("critico")
    assert len(rep.rutas) == PERFILES["critico"].repeticiones


def test_info_suena_una_vez():
    rep = _Reproductor()
    _player(rep).reproducir("info")
    assert len(rep.rutas) == 1


def test_ruta_apunta_al_asset_de_la_severidad():
    rep = _Reproductor()
    _player(rep, assets_dir=Path("/x/assets")).reproducir("critico")
    assert rep.rutas[0] == Path("/x/assets") / PERFILES["critico"].asset


def test_deshabilitado_no_suena():
    rep = _Reproductor()
    _player(rep, habilitado=False).reproducir("critico")
    assert rep.rutas == []


def test_espera_entre_repeticiones():
    rep = _Reproductor()
    esperas: list[float] = []
    _player(rep, sleep=lambda s: esperas.append(s)).reproducir("atencion")
    # Una espera menos que repeticiones (no se espera tras el último toque).
    assert len(esperas) == PERFILES["atencion"].repeticiones - 1


def test_fallo_del_reproductor_no_propaga():
    rep = _Reproductor(falla=True)
    _player(rep).reproducir("critico")  # no debe lanzar (RNF-03)
    assert len(rep.rutas) == PERFILES["critico"].repeticiones  # intentó todas


# --- Selección de reproductor por SO (pura) ---


def test_comando_linux_prefiere_paplay():
    assert comando_reproductor("/a.wav", "linux", {"paplay", "aplay"}) == ["paplay", "/a.wav"]


def test_comando_linux_cae_a_aplay():
    assert comando_reproductor("/a.wav", "linux", {"aplay"}) == ["aplay", "/a.wav"]


def test_comando_macos_usa_afplay():
    assert comando_reproductor("/a.wav", "darwin", set()) == ["afplay", "/a.wav"]


def test_comando_sin_reproductor_es_none():
    assert comando_reproductor("/a.wav", "linux", set()) is None
