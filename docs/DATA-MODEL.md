# Data Model — Vigía-eew

| Campo | Valor |
|---|---|
| Documento | Modelo de datos: evento normalizado, estado persistido y configuración |
| Versión | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación |
| Relacionado | `API-SPEC.md` (mapeo de fuentes), `PRD.md` (RF-07, RF-06, RF-10, RF-24), `TECHNICAL-DESIGN.md` |

> Todas las estructuras se validan con **pydantic** (v2). Los tipos aquí son el contrato vinculante
> para el código. Persistencia en **JSON**; configuración en **`config.toml`**.

---

## 1. Entidad: Evento sísmico normalizado (`SeismicEvent`)

Contrato interno que circula entre capas (RF-07). Producido por `Normalizer`, consumido por
`GeoFilter`, `Deduplicator` y la capa de notificación.

| Campo | Tipo | Obligatorio | Descripción | Origen |
|---|---|---|---|---|
| `id` | `str` | sí | Identificador estable por fuente (`unid` EMSC / `id` USGS) | fuente |
| `fuente` | `Literal["EMSC","USGS","SIMULADO"]` | sí | Origen del evento | sistema |
| `magnitud` | `float` | sí | Magnitud | fuente |
| `mag_type` | `str` | sí | Tipo de magnitud (`mw`,`mb`,`ml`…), normalizado a minúscula | fuente |
| `lugar` | `str \| None` | no | Descripción textual (USGS `place`) | fuente |
| `region` | `str \| None` | no | Región Flynn (EMSC `flynn_region`) o derivada | fuente |
| `lat` | `float` (−90..90) | sí | Latitud del epicentro | fuente |
| `lon` | `float` (−180..180) | sí | Longitud del epicentro | fuente |
| `profundidad_km` | `float` (≥0) | sí | Profundidad | fuente |
| `hora_utc` | `datetime` (tz-aware UTC) | sí | Tiempo de origen | fuente |
| `lastupdate_utc` | `datetime \| None` | no | Última actualización/revisión | fuente |
| `distancia_km` | `float` (≥0) | sí | Distancia al punto de referencia (haversine) | derivado |
| `severidad` | `Literal["info","atencion","critico"]` | sí | Nivel por magnitud (config) | derivado |
| `accion` | `Literal["create","update"]` | sí | Tipo de mensaje (default `create`) | fuente/sistema |

### 1.1 Definición pydantic (referencia)
```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class SeismicEvent(BaseModel):
    id: str
    fuente: Literal["EMSC", "USGS", "SIMULADO"]
    magnitud: float
    mag_type: str
    lugar: str | None = None
    region: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    profundidad_km: float = Field(ge=0)
    hora_utc: datetime                       # siempre tz-aware UTC
    lastupdate_utc: datetime | None = None
    distancia_km: float = Field(ge=0)
    severidad: Literal["info", "atencion", "critico"]
    accion: Literal["create", "update"] = "create"
```

### 1.2 Reglas e invariantes
- `hora_utc`/`lastupdate_utc` **siempre UTC tz-aware**. La conversión a `America/Caracas` ocurre solo
  en la presentación (RF-18, RNF-12), nunca en el modelo.
- `distancia_km` y `severidad` son **derivados** (no provienen de la fuente).
- `mag_type` se normaliza siempre a minúscula (resuelve EMSC `magtype` vs USGS `magType`).
- USGS entrega `time`/`updated` en **epoch ms** → convertir; EMSC en **ISO-8601** → parsear.

### 1.3 Severidad (derivación) — RF-13
Umbrales configurables; por defecto:

| Severidad | Rango de magnitud | Color | Sonido |
|---|---|---|---|
| `info` | `< 4.0` | azul/gris | suave, 1 toque |
| `atencion` | `4.0 – 5.5` | ámbar | medio, repetido |
| `critico` | `≥ 5.5` | rojo | fuerte, insistente |

---

## 2. Estado persistido (`AppState`) — RF-06, RF-10

Sobrevive reinicios; evita re-alertar y permite reconciliar (RF-10, RF-06). Guardado como **JSON**
con escritura atómica.

| Campo | Tipo | Descripción |
|---|---|---|
| `version` | `int` | Versión del esquema de estado (migraciones futuras) |
| `cursor_usgs_ms` | `int \| None` | Epoch ms del evento USGS más reciente procesado (cursor RF-06) |
| `ids_alertados` | `list[AlertedId]` | Ids ya alertados (con poda por antigüedad) |
| `firmas_recientes` | `list[EventSignature]` | Firmas para dedup inter-fuente (ventana temporal) |

```python
class AlertedId(BaseModel):
    id: str
    fuente: str
    hora_utc: datetime
    reconocido_utc: datetime | None = None    # auditoría del acknowledge

class EventSignature(BaseModel):
    lat: float
    lon: float
    hora_utc: datetime
    magnitud: float

class AppState(BaseModel):
    version: int = 1
    cursor_usgs_ms: int | None = None
    ids_alertados: list[AlertedId] = []
    firmas_recientes: list[EventSignature] = []
```

### 2.1 Ubicación (multiplataforma, vía `platformdirs`)
| SO | Ruta |
|---|---|
| Linux | `~/.local/share/vigia-eew/state.json` |
| Windows | `%LOCALAPPDATA%\vigia-eew\state.json` |
| macOS | `~/Library/Application Support/vigia-eew/state.json` |

### 2.2 Política de poda
- `ids_alertados` y `firmas_recientes` se podan por antigüedad (p. ej. > 24 h) para acotar tamaño.
- Escritura **atómica**: archivo temporal + `os.replace` (evita corrupción ante caída).

---

## 3. Configuración (`config.toml` → `Settings`) — RF-24

Leída con `tomllib` (stdlib 3.11+) y validada con **pydantic**. *Defaults* sensatos centrados en Caracas.

### 3.1 `config.toml` de ejemplo
```toml
[referencia]
nombre = "Caracas"
lat = 10.4806
lon = -66.9036

[filtro]
radio_km = 300.0
magnitud_minima = 2.5

[fuentes.emsc]
habilitado = true
url = "wss://www.seismicportal.eu/standing_order/websocket"
ping_interval_s = 15
ping_timeout_s = 20
backoff_max_s = 60

[fuentes.usgs]
habilitado = true
url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
intervalo_poll_s = 60
timeout_s = 15

[dedup]
distancia_km = 100.0
ventana_s = 90
delta_magnitud = 0.5

[severidad]
# límite superior de cada nivel; el resto es "critico"
info_max = 4.0
atencion_max = 5.5

[notificacion]
pantalla_completa = false
zona_horaria = "America/Caracas"
sonido = true

[logging]
nivel = "INFO"
archivo = "vigia-eew.log"
max_bytes = 1048576
backups = 3
```

### 3.2 Definición pydantic (referencia)
```python
from pydantic import BaseModel, Field

class Referencia(BaseModel):
    nombre: str = "Caracas"
    lat: float = Field(10.4806, ge=-90, le=90)
    lon: float = Field(-66.9036, ge=-180, le=180)

class Filtro(BaseModel):
    radio_km: float = Field(300.0, gt=0)
    magnitud_minima: float = Field(2.5, ge=0)

class FuenteEMSC(BaseModel):
    habilitado: bool = True
    url: str = "wss://www.seismicportal.eu/standing_order/websocket"
    ping_interval_s: int = 15
    ping_timeout_s: int = 20
    backoff_max_s: int = 60

class FuenteUSGS(BaseModel):
    habilitado: bool = True
    url: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    intervalo_poll_s: int = 60
    timeout_s: int = 15

class Dedup(BaseModel):
    distancia_km: float = 100.0
    ventana_s: int = 90
    delta_magnitud: float = 0.5

class Severidad(BaseModel):
    info_max: float = 4.0
    atencion_max: float = 5.5

class Notificacion(BaseModel):
    pantalla_completa: bool = False
    zona_horaria: str = "America/Caracas"
    sonido: bool = True

class LoggingCfg(BaseModel):
    nivel: str = "INFO"
    archivo: str = "vigia-eew.log"
    max_bytes: int = 1_048_576
    backups: int = 3

class Settings(BaseModel):
    referencia: Referencia = Referencia()
    filtro: Filtro = Filtro()
    fuentes_emsc: FuenteEMSC = FuenteEMSC()
    fuentes_usgs: FuenteUSGS = FuenteUSGS()
    dedup: Dedup = Dedup()
    severidad: Severidad = Severidad()
    notificacion: Notificacion = Notificacion()
    logging: LoggingCfg = LoggingCfg()
```

### 3.3 Resolución de la ruta de config
1. Flag CLI `--config <ruta>` (máxima prioridad).
2. `config.toml` en el directorio de config del usuario (`platformdirs`).
3. *Defaults* embebidos si no existe archivo (el agente arranca sin configuración previa).

---

## 4. Evento simulado (`--simulate`) — RF-21

Inyecta un `SeismicEvent` con `fuente="SIMULADO"` para validar la notificación sin sismo real.
Valores por defecto (configurables por flags):

```python
SeismicEvent(
    id="SIM-0001",
    fuente="SIMULADO",
    magnitud=6.1,
    mag_type="mw",
    lugar="cerca de La Guaira, Venezuela",
    region="NEAR COAST OF VENEZUELA",
    lat=10.60, lon=-66.93,
    profundidad_km=10.0,
    hora_utc="<ahora UTC>",
    distancia_km="<calculada>",
    severidad="critico",
    accion="create",
)
```

## 5. Diccionario de tipos y unidades

| Concepto | Unidad | Notas |
|---|---|---|
| Magnitud | escala del `mag_type` | comparaciones de dedup usan Δ absoluta |
| Distancia | km | haversine; radio terrestre 6371 km |
| Profundidad | km | ≥ 0 |
| Tiempo interno | UTC tz-aware | conversión a local solo en UI |
| Cursor USGS | epoch ms | igual unidad que `properties.time/updated` |

## 6. Trazabilidad

`SeismicEvent` ⇄ RF-07/RF-08/RF-13 · `AppState` ⇄ RF-06/RF-10 · `Settings` ⇄ RF-24/RF-12.
Mapeo de campos por fuente en `API-SPEC.md §3.1`.
