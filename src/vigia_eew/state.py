"""Persistencia de estado (RF-06, RF-10).

`StateStore` guarda y carga `AppState` como JSON con **escritura atómica** (archivo
temporal + `os.replace`) para no corromper el archivo ante una caída. Mantiene los
`ids_alertados` (para no repetir alertas tras reinicios, RF-10) y el `cursor_usgs`
(para reconciliar sin reprocesar histórico, RF-06). Aplica poda por antigüedad.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from platformdirs import user_data_dir

from .config import APP_NAME
from .models import AlertedId, AppState, EventSignature

NOMBRE_ARCHIVO_ESTADO = "state.json"
# Antigüedad máxima de ids/firmas antes de podarlos (DATA-MODEL §2.2).
ANTIGUEDAD_MAX = timedelta(hours=24)


def ruta_estado_predeterminada() -> Path:
    """Ruta de `state.json` en el directorio de datos del usuario (multiplataforma)."""
    return Path(user_data_dir(APP_NAME)) / NOMBRE_ARCHIVO_ESTADO


class StateStore:
    """Almacén de estado persistente con escritura atómica."""

    def __init__(self, ruta: Path | str | None = None) -> None:
        self.ruta = Path(ruta) if ruta is not None else ruta_estado_predeterminada()
        self._estado: AppState = AppState()

    @property
    def estado(self) -> AppState:
        return self._estado

    def cargar(self) -> AppState:
        """Carga el estado desde disco. Si no existe o está corrupto, parte de cero.

        La robustez es deliberada (RNF-03): un `state.json` corrupto no debe impedir
        que el agente arranque; se descarta y se reinicia el estado.
        """
        if not self.ruta.exists():
            self._estado = AppState()
            return self._estado
        try:
            data = json.loads(self.ruta.read_text(encoding="utf-8"))
            self._estado = AppState.model_validate(data)
        except (json.JSONDecodeError, ValueError, OSError):
            # Estado corrupto o ilegible: empezar limpio en lugar de fallar.
            self._estado = AppState()
        return self._estado

    def guardar(self) -> None:
        """Persiste el estado a disco de forma atómica."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        # pydantic v2: serialización JSON con datetimes en ISO-8601.
        contenido = self._estado.model_dump_json(indent=2)
        # Escritura atómica: escribir a temporal en el mismo directorio y reemplazar.
        fd, tmp = tempfile.mkstemp(dir=self.ruta.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(contenido)
            os.replace(tmp, self.ruta)  # atómico en el mismo sistema de archivos
        except BaseException:
            # Limpiar el temporal si algo falla antes del replace.
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # --- Operaciones de dominio ---

    def ya_alertado(self, id_evento: str) -> bool:
        """Indica si un id de evento ya fue alertado (RF-10)."""
        return any(a.id == id_evento for a in self._estado.ids_alertados)

    def registrar_alertado(self, alerta: AlertedId) -> None:
        """Añade un id alertado si no estaba ya presente."""
        if not self.ya_alertado(alerta.id):
            self._estado.ids_alertados.append(alerta)

    def marcar_reconocido(self, id_evento: str, cuando: datetime | None = None) -> None:
        """Registra el reconocimiento (acknowledge) de una alerta (auditoría, OBJ-1)."""
        cuando = cuando or datetime.now(UTC)
        for a in self._estado.ids_alertados:
            if a.id == id_evento:
                a.reconocido_utc = cuando
                break

    def agregar_firma(self, firma: EventSignature) -> None:
        """Guarda una firma reciente para la dedup inter-fuente (RF-09)."""
        self._estado.firmas_recientes.append(firma)

    def actualizar_cursor_usgs(self, cursor_ms: int) -> None:
        """Avanza el cursor de USGS al máximo visto (RF-06)."""
        actual = self._estado.cursor_usgs_ms
        if actual is None or cursor_ms > actual:
            self._estado.cursor_usgs_ms = cursor_ms

    def podar(self, ahora: datetime | None = None) -> None:
        """Elimina ids y firmas más antiguos que `ANTIGUEDAD_MAX` (DATA-MODEL §2.2)."""
        ahora = ahora or datetime.now(UTC)
        limite = ahora - ANTIGUEDAD_MAX
        self._estado.ids_alertados = [a for a in self._estado.ids_alertados if a.hora_utc >= limite]
        self._estado.firmas_recientes = [
            f for f in self._estado.firmas_recientes if f.hora_utc >= limite
        ]
