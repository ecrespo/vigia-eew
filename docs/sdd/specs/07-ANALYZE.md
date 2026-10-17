# Analyze — Vigía-eew v2 · 2026-09-06

Validación cruzada **de solo lectura** sobre los siete artefactos del kit, la constitución y los
documentos de los pasos previos (`docs/reverse-sdd/`, `docs/code-audit/`, `docs/arch-eval/`).
No corrige nada: presenta hallazgos. **La aprobación es humana.**

Comprobaciones automatizadas ejecutadas: definición/citación de REQ, IDs duplicados, enlaces
relativos, rutas citadas, y contraste de 14 cifras clave entre los 61 documentos del repositorio.

---

## Hallazgos

| # | Severidad | Categoría | Hallazgo | Artefactos | Sugerencia |
|---|---|---|---|---|---|
| A-01 | **ALTO** | Ambigüedad | REQ-ALE-004 está marcado `[MUST]` pero el Plan F4 contempla degradarlo a `[MAY]` si el spike falla. Un MUST condicional no es verificable: o bloquea el release o no | PRD §3, Plan F4 | Dejarlo `[MUST]` y que el spike decida **cómo** cumplirlo (D-Bus, portal, o cliente nativo), no **si** se cumple; o bajarlo a `[SHOULD]` y que REQ-ALE-003 (declarar el alcance) sea el MUST |
| A-02 | **ALTO** | Ejecutabilidad | T-003 modifica `pyproject.toml`, que T-001 crea, pero está marcada **[P]** y sin `Depende de` | Tasks F0 | Añadir `Depende de: T-001` a T-003 y retirar su `[P]`, o mover la configuración de cobertura a un archivo propio |
| A-03 | MEDIO | Terminología | Convención de ID inconsistente: `REQ-UX-NNN` usa área de **2** letras; los otros 50 usan **3**. Cualquier herramienta con un patrón de ancho fijo pierde 6 requisitos — le pasó al primer verificador de este mismo Analyze | PRD §8 | Declarar la convención como `REQ-{2,3 letras}-{NNN}` con su expresión regular canónica, o renombrar el área |
| A-04 | MEDIO | Consistencia numérica | "59 commits" (`docs/code-audit/`) frente a "58 commits" (`docs/reverse-sdd/`). **Ambos son correctos**: 58 es el historial de `HEAD`, 59 incluye las tres ramas (`main`, `develop`, `documentation`) que barrió el escaneo de secretos. El alcance no está declarado en ninguno | code-audit, reverse-sdd | Añadir el alcance a cada cifra: "58 en `HEAD`" / "59 en todas las ramas" |
| A-05 | MEDIO | Consistencia numérica | "344 tests en **35** archivos" (`docs/code-audit/`) frente a "344 funciones de test en **37** archivos" (`docs/reverse-sdd/` ×3). Ambos ciertos: 35 archivos `test_*.py`, 37 `.py` en `tests/` contando `conftest.py` e `__init__.py` | code-audit, reverse-sdd | Unificar a "35 archivos `test_*.py`" |
| A-06 | BAJO | Terminología | El Tech Design §8 dice "las 157 **pruebas**"; el término canónico del kit es "casos de prueba" (157), reservando "pruebas/tests" para las 344 funciones existentes. Conflatarlos invita a comparar magnitudes distintas | Tech Design §8 | Sustituir por "casos de prueba" |
| A-07 | BAJO | Referencias | Cuatro referencias abreviadas entre comillas invertidas (el ADR-001 de la evaluación arquitectónica, HU-016) se leen como rutas y no resuelven porque les falta la extensión y el sufijo del nombre | Tech Design, Data Model | Usar el enlace markdown completo, que sí resuelve |
| A-08 | BAJO | Referencias | el futuro `src/vigia_eew/wiring.py` se cita como ruta existente en `docs/arch-eval/` y en el Tech Design; es un archivo **propuesto**, aún inexistente | arch-eval, Tech Design | Marcarlo como propuesto ("futuro `wiring.py`") para que un verificador de rutas no lo señale |

**Ningún hallazgo CRÍTICO.**

---

## Resultado por categoría del checklist

### 1. Cobertura — ✅ con una salvedad
- Los **56 REQ** del PRD están definidos, sin IDs duplicados y sin REQ fantasma citado en Tasks.
- Los **26 REQ** de las fases 0-2 tienen tarea; los **24** restantes están **explícitamente
  listados como diferidos**, con su fase de destino nombrada.
- Las 9 fases del plan cubren las 7 áreas de requisitos. Las fases 3-8 generan sus tareas al
  llegar, por decisión declarada en el propio archivo de Tasks — no es un hueco, es un límite de
  lote (el skill recomienda 8-25 tareas por archivo; 56 REQ de una vez darían más de 100).
- **Salvedad:** los REQ de las fases 3-8 no tienen todavía test planificado nominal. Su cobertura
  descansa en los 157 casos de prueba de `docs/reverse-sdd/04-MATRIZ-PRUEBAS.md`, de las cuales **143 ya
  existen** en la v0.6.0 y se portan; **14 hay que escribirlas**.

### 2. Constitución — ✅
Ningún artefacto contradice un artículo. **Una sola excepción solicitada**, con justificación
escrita (PRD §11): consumir el endpoint de FUNVISIS sin TLS. Cumple la forma que exige el Art. 8:
declarada, razonada y acotada.

### 3. Ambigüedad — ⚠️ un hallazgo (A-01)
Los criterios nuevos nombran resultados observables (fan-out ≤ 8, "toca exactamente 3 puntos", "una
búsqueda por `corr=` reconstruye el recorrido", "un PNG inválido hace fallar el build"). Los límites
llevan valor y unidad: 2 s de tiempo límite en D-Bus, 3 días de spike, 24 h de retención, umbrales
de cobertura 85/70/40 %. El único criterio no verificable como está escrito es REQ-ALE-004 (A-01).

### 4. Consistencia terminológica — ⚠️ tres hallazgos (A-03, A-04, A-05)
El vocabulario de dominio es estable en los 61 documentos: *evento sísmico / alerta / fuente /
deduplicación / frescura / punto de referencia*. Las desviaciones son de **cifras y de convención de
ID**, no de conceptos.

### 5. Caminos no felices — ✅
Las cuatro integraciones externas tienen sus `SI...ENTONCES` (REQ-ING-006, ING-007), y también el
servicio D-Bus (API Spec §4: no registrado, sin respuesta en 2 s, bus no disponible), los efectos
auxiliares (REQ-ALE-010), los filtros mal configurados (REQ-PIP-006) y el estado corrupto
(REQ-CFG-002). **La idempotencia está cubierta** por la deduplicación (REQ-PIP-008) y por la
idempotencia de `Present` por `alert['id']` en el contrato D-Bus.

### 6. Datos — ✅
No hay dinero ni Decimal que discutir. Fechas con zona explícita e invariante propia (INV-1).
Formato de ID definido (ULID de 26 caracteres). **Sin índices que revisar**: no hay motor de
consultas, y el Data Model §6 lo declara con su condición de reevaluación. La migración de estado
v0.6.0 → v2 está especificada (§4), incluido el comportamiento ante un downgrade.

### 7. Ejecutabilidad de las tareas — ⚠️ un hallazgo (A-02)
17 tareas, todas con REQ y con "Done" ejecutable. Primera tanda identificada (T-001..T-005) y tres
de ellas con **comprobación negativa obligatoria**, que es lo que distingue un gate real de uno
decorativo. Sin ciclos en las dependencias. El único defecto es el `[P]` de T-003 (A-02).

---

## Correspondencia RF (v0.6.0) ↔ REQ (v2)

Los identificadores `RF-xx` de `docs/PRD.md` siguen designando el sistema en producción. Mapa de
áreas, para que una discusión sobre "RF-40" se sepa traducir:

| RF (v0.6.0) | REQ (v2) | Nota |
|---|---|---|
| RF-01..RF-06 (ingesta, cursores) | REQ-ING-001..004, REQ-CFG-004 | Sin cambio funcional |
| RF-07, RF-13 (modelo, severidad) | REQ-PIP-001 | Se añade `correlation_id` |
| RF-09..RF-11 (dedup, update) | REQ-PIP-008, 009, REQ-ALE-006 | Heurística idéntica |
| RF-12 (radio y magnitud) | REQ-PIP-003 | Sin cambio |
| RF-14..RF-21 (notificación) | REQ-ALE-001..010 | Se añaden ALE-003 y ALE-004 (Wayland) |
| RF-22, RF-23 (autoarranque) | REQ-OPS-004 | Sin cambio |
| RF-24..RF-30 (config, empaquetado) | REQ-CFG-005, 006, REQ-OPS-006..008 | Se añaden OPS-007 y OPS-008 |
| RF-33 (ubicación por IP) | REQ-CFG-007 | Sin cambio |
| RF-34 (bandeja) | REQ-UX-004 | Sin cambio |
| RF-35 (i18n) | REQ-UX-001..003 | UX-003 exige inglés **desde la fase 1** |
| RF-36 (TUI) | REQ-UX-005 | Sin cambio |
| RF-37 (filtro de país) | REQ-PIP-005 | Sin cambio |
| RF-38, RF-39 (FUNVISIS, GEOFON) | REQ-ING-005, 008 | Sin cambio |
| RF-40..RF-42 (frescura, backlog, poda) | REQ-PIP-004, REQ-ING-004, REQ-CFG-003 | Elevados a invariantes del Data Model |
| — | REQ-OBS-002..005, REQ-OPS-003 | **Sin RF equivalente**: nacen de las auditorías |

Ningún RF de la v0.6.0 queda sin REQ correspondiente. Ningún ID se reutiliza.

---

## Veredicto

> **CORREGIR LOS DOS ALTOS PRIMERO** — luego listo para implementar.

- **A-01** es de diseño y necesita una decisión humana: si REQ-ALE-004 es un MUST, el spike decide
  *cómo* cumplir el Art. 1 bajo Wayland, no *si* se cumple. La respuesta cambia el alcance de la
  Fase 4, que ya es la de mayor riesgo del plan.
- **A-02** es mecánico: un `Depende de` que falta en T-003.
- Los seis hallazgos MEDIO y BAJO son de consistencia documental y no bloquean la implementación;
  se abordan en la pasada de consistencia global (`docs/sdd/08-CONSISTENCIA.md`, generado tras este Analyze).

**Lo que este Analyze NO pudo verificar** y queda pendiente hasta que exista código de la v2:
que cada criterio tenga un test que lo cite por REQ-ID (Art. 8). Hoy solo es verificable la
existencia de las **143 pruebas heredadas** (de las 344 existentes); la trazabilidad test→REQ es una convención nueva que
empieza a regir con T-001.
