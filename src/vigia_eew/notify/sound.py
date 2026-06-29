"""Capa de audio de la alerta (RF-17, ADR-005).

Reproduce un sonido por severidad, **más insistente cuanto más grave** (más
repeticiones). El reproductor real depende del SO (paplay/aplay/ffplay en Linux,
afplay en macOS, `winsound` en Windows) con *fallback* a la campana del terminal;
esa elección se aísla en `comando_reproductor` (pura) y en `_reproductor_por_defecto`.

El reproductor es inyectable para probar la lógica de repetición sin reproducir audio.
Un fallo al reproducir nunca interrumpe la alerta (RNF-03): se registra y se continúa.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..models import Severidad

_Reproductor = Callable[[Path], None]
_SleepFn = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class PerfilSonido:
    """Perfil de reproducción de una severidad: asset y patrón de repetición."""

    asset: str
    repeticiones: int
    intervalo_s: float


# Insistencia creciente con la severidad (RF-17).
PERFILES: dict[Severidad, PerfilSonido] = {
    "info": PerfilSonido("info.wav", 1, 0.0),
    "atencion": PerfilSonido("atencion.wav", 2, 0.6),
    "critico": PerfilSonido("critico.wav", 4, 0.4),
}


def ruta_assets() -> Path:
    """Directorio de assets de audio empaquetados (`vigia_eew/assets`)."""
    return Path(__file__).resolve().parent.parent / "assets"


def comando_reproductor(
    ruta: str | Path, plataforma: str, disponibles: set[str]
) -> list[str] | None:
    """Elige el comando de reproducción según SO y binarios disponibles.

    Devuelve la lista de argumentos para `subprocess`, o None si no hay reproductor
    externo adecuado (el llamador usará un *fallback*).
    """
    ruta = str(ruta)
    if plataforma == "darwin":
        return ["afplay", ruta]
    if plataforma == "win32":
        return None  # en Windows se usa `winsound`, no un comando externo
    if "paplay" in disponibles:
        return ["paplay", ruta]
    if "aplay" in disponibles:
        return ["aplay", ruta]
    if "ffplay" in disponibles:
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", ruta]
    return None


def _disponibles() -> set[str]:
    return {c for c in ("paplay", "aplay", "ffplay") if shutil.which(c)}


def _reproductor_por_defecto(ruta: Path) -> None:
    """Reproductor real por SO; *fallback* a la campana del terminal."""
    if sys.platform == "win32":
        import winsound  # solo disponible en Windows

        winsound.PlaySound(str(ruta), winsound.SND_FILENAME)
        return
    comando = comando_reproductor(ruta, sys.platform, _disponibles())
    if comando is None:
        print("\a", end="", flush=True)  # campana del terminal como último recurso
        return
    subprocess.run(comando, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class SoundPlayer:
    """Reproduce el sonido de alerta según la severidad (RF-17)."""

    def __init__(
        self,
        *,
        reproductor: _Reproductor | None = None,
        sleep: _SleepFn = time.sleep,
        habilitado: bool = True,
        assets_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._reproductor = reproductor or _reproductor_por_defecto
        self._sleep = sleep
        self._habilitado = habilitado
        self._assets_dir = assets_dir or ruta_assets()
        self._log = logger or logging.getLogger("vigia_eew.notify.sound")

    def reproducir(self, severidad: Severidad) -> None:
        """Reproduce el perfil de la severidad (varias veces si es insistente)."""
        if not self._habilitado:
            return
        perfil = PERFILES[severidad]
        ruta = self._assets_dir / perfil.asset
        for i in range(perfil.repeticiones):
            try:
                self._reproductor(ruta)
            except Exception as exc:  # noqa: BLE001 - el audio nunca rompe la alerta
                self._log.warning("sonido_fallo detalle=%s", exc)
            if i < perfil.repeticiones - 1:
                self._sleep(perfil.intervalo_s)
