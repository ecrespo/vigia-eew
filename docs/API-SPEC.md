# API Spec — Contratos de fuentes y evento normalizado

| Campo | Valor |
|---|---|
| Documento | Contrato de las fuentes que consume Vigía + esquema interno normalizado |
| Versión | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación |
| Relacionado | `PRD.md` (RF-01..RF-11), `DATA-MODEL.md`, `ARCHITECTURE.md` |

> Vigía **consume** dos contratos externos (entrada) y define **un** contrato interno (el evento
> normalizado) que el resto del sistema produce y consume. No expone ninguna API de red propia en
> v1. Los contratos externos se verificaron contra los endpoints en vivo el 2026-06-28.

---

## 1. Fuente PRIMARIA — WebSocket EMSC (push real)

### 1.1 Endpoint y transporte
- **URL**: `wss://www.seismicportal.eu/standing_order/websocket`
- **Transporte**: WebSocket (RFC 6455). Servido también vía SockJS (`/standing_order`), pero el cliente Python usa el endpoint **`/websocket`** directo con la librería `websockets`.
- **Autenticación**: ninguna (público, gratuito).
- **Dirección**: solo servidor→cliente. El cliente no envía mensajes de datos; solo frames de control (ping/pong).

### 1.2 Keepalive (OBLIGATORIO) — RF-02
El socket muere **en silencio** sin keepalive. Debe enviarse un **ping cada ~15 s**
(`PING_INTERVAL = 15`, confirmado en el ejemplo oficial de EMSC). Con la librería `websockets`:

```python
async with websockets.connect(
    "wss://www.seismicportal.eu/standing_order/websocket",
    ping_interval=15,   # envía ping cada 15 s
    ping_timeout=20,    # cierra si no hay pong → dispara reconexión
) as ws:
    async for raw in ws:
        ...
```

### 1.3 Formato del mensaje
Cada mensaje es un **texto JSON**. Estructura confirmada:

```json
{
  "action": "create",
  "data": {
    "type": "Feature",
    "geometry": { "type": "Point", "coordinates": [-66.90, 10.48, 12.0] },
    "id": "20260628_0000123",
    "properties": {
      "lat": 10.48,
      "lon": -66.90,
      "depth": 12.0,
      "mag": 6.1,
      "magtype": "mw",
      "time": "2026-06-28T13:39:00.0Z",
      "lastupdate": "2026-06-28T13:41:00.0Z",
      "auth": "INGV",
      "unid": "20260628_0000123",
      "flynn_region": "NEAR COAST OF VENEZUELA",
      "evtype": "ke"
    }
  }
}
```

| Campo del mensaje | Tipo | Significado | Uso en Vigía |
|---|---|---|---|
| `action` | enum `create` \| `update` | Evento insertado o corregido | `create`→posible alerta nueva; `update`→actualizar sin re-alertar (RF-11) |
| `data` | Feature GeoJSON | El evento | Fuente de la normalización |
| `data.properties.unid` | string | **Identificador único** del evento | `id` interno; clave de dedup intra-EMSC |
| `data.properties.mag` | number | Magnitud | `magnitud` |
| `data.properties.magtype` | string (**minúscula**) | Tipo de magnitud (`mw`, `mb`, `ml`…) | `magType` (⚠️ se normaliza el nombre) |
| `data.properties.lat` / `lon` | number | Coordenadas | `lat` / `lon` |
| `data.properties.depth` | number | Profundidad (km) | `profundidad_km` |
| `data.properties.time` | ISO-8601 UTC | Tiempo de origen | `hora_utc` |
| `data.properties.lastupdate` | ISO-8601 UTC | Última actualización | control de versión del evento |
| `data.properties.auth` | string | Agencia autora (INGV, GFZ…) | metadato/auditoría |
| `data.properties.flynn_region` | string | Región Flynn-Engdahl | `region`/`lugar` |

> ⚠️ **Particularidades**: EMSC usa `magtype` (minúscula); las coordenadas en `geometry.coordinates`
> siguen el orden GeoJSON **[lon, lat, depth]**. Se prefieren los campos de `properties` (`lat`,
> `lon`, `depth`) por claridad, usando `geometry` como verificación.

### 1.4 Comportamiento y límites conocidos
- El WS arrastra eventos de **muchas agencias** (incluye sismos pequeños globales) → el filtrado geográfico/magnitud es del lado del cliente (RF-12).
- **PUEDE PERDER MENSAJES** (timeouts y ráfagas documentadas). Por eso existe el respaldo USGS (RF-05).
- Puede emitir varios `update` para un mismo `unid` (refinamiento de magnitud/localización).
- No hay *replay* de historial al reconectar: lo perdido durante una caída se recupera por USGS.

---

## 2. Fuente de RESPALDO — USGS FDSN (polling de baja frecuencia)

### 2.1 Endpoint
```
GET https://earthquake.usgs.gov/fdsnws/event/1/query
```
**Único fin**: (a) recuperar eventos regionales que el WS dejó pasar y (b) cubrir sismos
locales pequeños. **No** es un segundo bucle del mismo peso que el WS. Frecuencia: **cada 60 s** (RF-05).

### 2.2 Parámetros de consulta
| Parámetro | Valor por defecto | Notas |
|---|---|---|
| `format` | `geojson` | Formato de salida |
| `latitude` | `10.4806` | Punto de referencia (Caracas) — de config |
| `longitude` | `-66.9036` | de config |
| `maxradiuskm` | `300` | Radio de interés — de config |
| `minmagnitude` | `2.5` | Magnitud mínima — de config (RF-12) |
| `orderby` | `time` | Más recientes primero |
| `eventtype` | `earthquake` | Solo sismos |
| `starttime` / `updatedafter` | **cursor persistido** | "desde el último evento visto" (RF-06) |
| `limit` | (opcional) | Acotar respuesta |

Ejemplo (verificado en vivo):
```
https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude=10.4806&longitude=-66.9036&maxradiuskm=300&minmagnitude=2.5&orderby=time&eventtype=earthquake
```

### 2.3 Estrategia de cursor (RF-06)
- Se persiste el `time` (epoch ms) del evento **más reciente ya procesado**.
- En cada poll se consulta con `starttime` = cursor (o `updatedafter` para capturar revisiones).
- Tras procesar, se avanza el cursor al `time` máximo visto. El cursor sobrevive a reinicios (ver `DATA-MODEL.md`).

### 2.4 Formato de respuesta (GeoJSON `FeatureCollection`)
Confirmado en vivo (recortado a campos relevantes):

```json
{
  "type": "FeatureCollection",
  "metadata": { "generated": 1782668911000, "title": "USGS Earthquakes", "status": 200, "api": "2.4.0" },
  "features": [
    {
      "type": "Feature",
      "id": "us6000t8sx",
      "properties": {
        "mag": 4.3,
        "place": "19 km WSW of Morón, Venezuela",
        "time": 1782639238852,
        "updated": 1782655565862,
        "magType": "mb",
        "status": "reviewed",
        "ids": ",us6000t8sx,",
        "sources": ",us,",
        "net": "us",
        "code": "6000t8sx",
        "type": "earthquake",
        "title": "M 4.3 - 19 km WSW of Morón, Venezuela"
      },
      "geometry": { "type": "Point", "coordinates": [-68.3766, 10.4497, 10] }
    }
  ]
}
```

| Campo | Tipo | Significado | Uso en Vigía |
|---|---|---|---|
| `id` (Feature) | string | Identificador USGS (`us6000t8sx`) | `id` interno; clave de dedup intra-USGS |
| `properties.mag` | number | Magnitud | `magnitud` |
| `properties.magType` | string (**camelCase**) | Tipo de magnitud | `magType` (⚠️ nombre distinto a EMSC) |
| `properties.place` | string | Descripción del lugar | `lugar` |
| `properties.time` | epoch **ms** | Tiempo de origen | `hora_utc` (convertir desde ms) |
| `properties.updated` | epoch **ms** | Última revisión | cursor `updatedafter` |
| `properties.status` | string | `reviewed`/`automatic` | metadato/calidad |
| `geometry.coordinates` | [lon, lat, depth_km] | Posición | `lon`, `lat`, `profundidad_km` |

> ⚠️ **Particularidades**: USGS usa `magType` (camelCase) y `time`/`updated` en **epoch milisegundos**;
> EMSC usa `magtype` (minúscula) y `time` ISO-8601. El normalizador resuelve ambas (ver §3 y `DATA-MODEL.md`).

### 2.5 Errores y resiliencia (RNF-03)
| Situación | Manejo |
|---|---|
| HTTP 429 (rate limit) | Respetar `Retry-After` si existe; backoff; el ciclo continúa. |
| HTTP 5xx | Reintento en el siguiente ciclo; log de advertencia; no abortar. |
| Timeout de red | `httpx` con timeout; saltar el ciclo; mantener cursor. |
| JSON inválido / esquema inesperado | Validar con pydantic; descartar Feature inválida; log; no terminar. |

---

## 3. Contrato INTERNO — Evento normalizado

Ambas fuentes se normalizan a **un esquema común** (RF-07). Es el contrato que circula entre las
capas (ingestión → dedup/filtro → notificación). Esquema canónico (detalle de tipos en `DATA-MODEL.md`):

```json
{
  "id": "us6000t8sx",
  "fuente": "USGS",
  "magnitud": 4.3,
  "magType": "mb",
  "lugar": "19 km WSW of Morón, Venezuela",
  "region": "NEAR COAST OF VENEZUELA",
  "lat": 10.4497,
  "lon": -68.3766,
  "profundidad_km": 10.0,
  "hora_utc": "2026-06-28T13:33:58.852Z",
  "distancia_km": 162.4,
  "severidad": "atencion",
  "lastupdate_utc": "2026-06-28T13:46:05.862Z"
}
```

### 3.1 Mapeo de campos por fuente

| Campo normalizado | EMSC (WS) | USGS (FDSN) |
|---|---|---|
| `id` | `properties.unid` | `id` (Feature) |
| `fuente` | `"EMSC"` | `"USGS"` |
| `magnitud` | `properties.mag` | `properties.mag` |
| `magType` | `properties.magtype` (↑a minúscula consistente) | `properties.magType` |
| `lugar` | — (usar `flynn_region`) | `properties.place` |
| `region` | `properties.flynn_region` | derivar de `place` |
| `lat` | `properties.lat` | `geometry.coordinates[1]` |
| `lon` | `properties.lon` | `geometry.coordinates[0]` |
| `profundidad_km` | `properties.depth` | `geometry.coordinates[2]` |
| `hora_utc` | `properties.time` (ISO-8601) | `properties.time` (epoch ms → ISO) |
| `lastupdate_utc` | `properties.lastupdate` | `properties.updated` (epoch ms → ISO) |
| `distancia_km` | calculada (haversine vs punto ref.) | calculada |
| `severidad` | calculada (por magnitud, config RF-13) | calculada |

### 3.2 Invariantes del contrato interno
- `id` es estable por fuente; la dedup **inter-fuente** usa la heurística (≤100 km, ≤90 s, ≤0.5 mag), no el `id` (RF-09).
- `hora_utc` siempre en UTC; la conversión a hora local (America/Caracas) ocurre **solo en la capa de presentación** (RF-18, RNF-12).
- `distancia_km` y `severidad` son **derivados**: se calculan en la normalización/filtro, nunca vienen de la fuente.

---

## 4. Fuente auxiliar — Geolocalización por IP (RF-33)

Usada **solo** cuando el usuario no define `[referencia]` en `config.toml`, para estimar un punto
de referencia geográfico razonable sin intervención manual. Es de "mejor esfuerzo": cualquier fallo
hace *fallback* al default (Caracas) sin bloquear el arranque (ver `geoloc.py`, `TECHNICAL-DESIGN.md`).

| Elemento | Valor |
|---|---|
| Endpoint | `https://ipapi.co/json/` (HTTPS, sin API key) |
| Método | `GET`, sin parámetros (la IP de origen la infiere el servicio) |
| Timeout | 5 s |
| Frecuencia | **Una vez** por instalación — el resultado se cachea en `state.json` (`ubicacion_detectada`) y no se repite en arranques siguientes salvo que se borre el estado o se defina `[referencia]` manual. |

### 4.1 Campos usados de la respuesta

| Campo JSON | Uso |
|---|---|
| `latitude`, `longitude` | `Referencia.lat` / `Referencia.lon` (obligatorios; si faltan o no son numéricos, se descarta la respuesta) |
| `city` | `Referencia.nombre`; si falta, se usa `country_name`; si tampoco, un nombre genérico |

### 4.2 Errores y resiliencia
| Situación | Manejo |
|---|---|
| Sin red / timeout / error HTTP | Se captura, se logea un *warning*, se devuelve `None` (fallback al default). |
| Status ≠ 200 | Igual que arriba. |
| JSON inválido o campos faltantes/fuera de rango | Igual que arriba; nunca lanza una excepción hacia el llamador. |

---

## 5. Evolución futura (no v1) — Relay central

Documentado en `TECHNICAL-DESIGN.md` (ADR-008): un relay FastAPI podría exponer un WebSocket propio
de *fan-out* hacia muchos clientes Vigía, reusando **el mismo contrato interno** de §3 como payload,
de modo que la migración no rompa el modelo de datos.

## 6. Evolución futura (no v1) — Contrato D-Bus (frontend GNOME opcional)

Documentado en `TECHNICAL-DESIGN.md` (ADR-010, elaboración detallada): el agente podría exponer un
servicio en el **bus de sesión** para que una extensión de GNOME Shell (u otro frontend local) se
suscriba a las alertas y confirme el reconocimiento, sin duplicar el esquema de §3.

| Elemento | Valor |
|---|---|
| Bus | Sesión (`DBUS_SESSION_BUS_ADDRESS`), no *system bus* |
| Nombre de servicio | `org.vigia_eew.Agente` |
| Ruta de objeto | `/org/vigia_eew/Agente` |
| Interfaz | `org.vigia_eew.Agente.Alertas1` (versionada) |

| Miembro | Firma | Payload |
|---|---|---|
| señal `AlertaNueva` | `(s)` | `SeismicEvent` JSON — mismo esquema de §3 |
| señal `AlertaActualizada` | `(s)` | `SeismicEvent` JSON, `accion="update"` (RF-11) |
| método `Reconocer` | `(s) -> (b)` | `id` del evento a reconocer |
| método `ObtenerActiva` | `() -> (s)` | `SeismicEvent` JSON en curso, o `""` si no hay ninguna |
| método `Ping` | `() -> (s)` | versión del agente, p. ej. `"1.0"` |

El payload de las señales es **el mismo JSON del contrato interno** (§3), serializado tal cual
(`model_dump_json()`); no se define una *struct* D-Bus paralela. Este contrato es aditivo a la
ventana Tk (ADR-003): no la reemplaza salvo que la extensión GNOME esté detectada y activa (ver
selección `frontend = "auto"` en `TECHNICAL-DESIGN.md`). **No implementado en v1.**
