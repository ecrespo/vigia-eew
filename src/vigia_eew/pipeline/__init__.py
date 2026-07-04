"""Pipeline de procesamiento: normalización → filtro → dedup (RF-07..RF-13).

Consume los `RawMessage` de la capa de ingestión y produce `SeismicEvent` listos para
notificar. Cada etapa es independiente y testeable por separado (TECHNICAL-DESIGN §2).
"""

from __future__ import annotations
