"""Configuración de logging (RF-25, RNF-07).

Logging estructurado a consola y a archivo rotativo. El formato incluye marca de
tiempo UTC, nivel, nombre del logger y mensaje en estilo clave=valor para facilitar
el análisis posterior. El archivo se ubica en el directorio de datos del usuario.
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

from .config import APP_NAME, LoggingCfg

_FORMATO = "%(asctime)sZ nivel=%(levelname)s logger=%(name)s %(message)s"
_FECHA = "%Y-%m-%dT%H:%M:%S"


class _FormatterUTC(logging.Formatter):
    """Formatter que emite timestamps en UTC (coherente con el modelo de datos)."""

    converter = staticmethod(time.gmtime)


def ruta_log_predeterminada(nombre_archivo: str) -> Path:
    """Devuelve la ruta del archivo de log en el directorio de logs del usuario."""
    directorio = Path(user_log_dir(APP_NAME))
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio / nombre_archivo


def configurar_logging(cfg: LoggingCfg | None = None, *, a_archivo: bool = True) -> logging.Logger:
    """Configura el logger raíz del agente.

    Args:
        cfg: parámetros de logging (nivel, archivo, rotación). Si es None, se usan defaults.
        a_archivo: si False, solo registra en consola (útil en tests).

    Returns:
        El logger raíz del paquete (`vigia_eew`).
    """
    cfg = cfg or LoggingCfg()
    nivel = getattr(logging, cfg.nivel.upper(), logging.INFO)

    logger = logging.getLogger("vigia_eew")
    logger.setLevel(nivel)
    logger.handlers.clear()  # idempotente: evita handlers duplicados al reconfigurar
    logger.propagate = False

    formatter = _FormatterUTC(_FORMATO, datefmt=_FECHA)

    consola = logging.StreamHandler()
    consola.setFormatter(formatter)
    logger.addHandler(consola)

    if a_archivo:
        ruta = ruta_log_predeterminada(cfg.archivo)
        archivo = RotatingFileHandler(
            ruta, maxBytes=cfg.max_bytes, backupCount=cfg.backups, encoding="utf-8"
        )
        archivo.setFormatter(formatter)
        logger.addHandler(archivo)
        logger.debug("logging_configurado ruta=%s", ruta)

    return logger
