# Constitución — Vigía-eew

> Versión 1.0 · Ratificada: 2026-09-06 · Última enmienda: 2026-09-19 (E-01..E-06)
> Ámbito: repositorio `ecrespo/vigia-eew`, todas las versiones a partir de la v2.
> Base empírica: `docs/reverse-sdd/`, `docs/code-audit/`, `docs/arch-eval/`.

Los principios no negociables del proyecto. Todo artefacto posterior se valida contra ellos
("constitution check"). No se relitigan por PR ni por feature; se enmiendan con changelog.

**Los nueve artículos son destilado de evidencia, no de opinión**: cada uno nace de algo que la
auditoría midió o que el historial demostró.

---

## Artículos

### Art. 1 — La alerta es el producto
EL SISTEMA DEBERÁ presentar toda alerta relevante de forma que solo un acuse explícito del usuario
la cierre, en **todos** los frontends que ofrezca, y DEBERÁ declarar por escrito el entorno de
escritorio en el que esa garantía no puede sostenerse.

*Racional: es OBJ-1 y la única razón de existir del agente. La segunda mitad del artículo existe
porque hoy la garantía no se cumple bajo Wayland y eso nunca se declaró — ver `docs/arch-eval/`
§7 y `docs/reverse-sdd/01-ARQUITECTURA.md` §7.*

### Art. 2 — Ningún evento se pierde; ninguna alerta se repite
EL SISTEMA DEBERÁ preferir una alerta espuria a una alerta perdida en toda decisión de diseño, y
DEBERÁ persistir lo ya alertado de modo que un reinicio no lo repita.

*Racional: OBJ-3. El coste es asimétrico — una alerta de más es una molestia, una de menos es el
producto fallando en el único momento para el que existe.*

### Art. 3 — Degradación fail-safe, nunca fail-closed
CUANDO un mecanismo auxiliar (bandeja, toast, geolocalización, filtro de país, frescura) no pueda
operar con confianza, EL SISTEMA DEBERÁ quedar inerte y registrar un aviso, y NO DEBERÁ suprimir
una alerta ni terminar el proceso.

*Racional: patrón ya establecido y verificado en cinco módulos (`docs/arch-eval/` atributo 4).
Elevarlo a artículo impide que la próxima feature lo rompa por descuido.*

### Art. 4 — Todo instante es UTC consciente de zona
EL SISTEMA DEBERÁ representar internamente todo `datetime` como tz-aware en UTC y DEBERÁ rechazar
valores naive en el borde. La conversión a hora local solo ocurre en la capa de presentación y en
el módulo de fronteras de día local.

*Racional: invariante ya validado en `models.py`. El cálculo de frescura por día local (RF-40)
demostró que mezclar zonas produce ventanas de error de cuatro horas.*

### Art. 5 — Las fronteras de módulo son ejecutables
EL SISTEMA DEBERÁ declarar sus fronteras de importación en una herramienta que las verifique
(import-linter o equivalente) y el CI DEBERÁ fallar ante un ciclo de dependencias nuevo o una
importación que cruce una capa en sentido prohibido.

*Racional: hoy hay 0 ciclos entre 40 módulos y 97 aristas, pero nada lo obliga — la disciplina se
sostiene solo sobre tener un único autor (`docs/arch-eval/` P2-2, ADR-003).*

### Art. 6 — El estado compartido entre hilos se declara y se sincroniza
DONDE un dato mutable sea accedido por más de un hilo, EL SISTEMA DEBERÁ protegerlo con una
primitiva de sincronización explícita y DEBERÁ documentar a qué hilo pertenece cada campo.

*Racional: `AgentState` lo hace bien con `threading.Lock`; `Application._loop`/`._sup` no, y de ahí
sale la única condición de carrera del sistema (`docs/arch-eval/` P2-1, ADR-002). La inconsistencia
del patrón es el defecto, no la carrera en sí.*

### Art. 7 — Toda dependencia inyectable, toda suite headless
EL SISTEMA DEBERÁ inyectar relojes, temporizadores, clientes de red, ejecutores de subprocesos y
efectos de notificación, de forma que la suite por defecto corra sin pantalla, sin audio, sin red
y sin esperas reales.

*Racional: es lo que permite 344 pruebas deterministas hoy. También es lo que hizo posible verificar
tres plataformas de autoarranque sin ninguna de ellas disponible.*

### Art. 8 — Nada entra sin gate verde, y el gate mide las ocho dimensiones
EL EQUIPO DEBERÁ mantener en verde lint, tipado estricto, pruebas **con umbral de cobertura**,
duplicación, complejidad, SAST, SCA y secretos antes de cada merge; ningún merge con hooks
deshabilitados.

*Racional: el gate actual cubre cinco de las ocho y mide cobertura sin exigirla
(`docs/code-audit/` P2-1, P2-2, P2-4). `StateStore.prune()` vivió 14 fases con test verde y cero
llamadas precisamente por eso.*

### Art. 9 — La especificación se actualiza en el mismo cambio que el código
EL EQUIPO DEBERÁ actualizar los artefactos de especificación afectados dentro del mismo commit o
PR que cambia el comportamiento, y DEBERÁ registrar toda decisión no obvia como ADR o sección de
`lat.md/` antes de cerrar la tarea.

*Racional: la disciplina ya existe (14 toques a `IMPLEMENTATION-PLAN.md` sincronizados con el
código), pero se rompió dos veces: ADR-015 y ADR-016 se escribieron retroactivamente, y el propio
Technical Design lo admite.*

---

## Restricciones del stack

Decidido; no se rediscute por feature.

| Área | Decisión | Mínimo |
|---|---|---|
| Lenguaje | Python | **≥ 3.13** (enmendado, E-01: 3.12 está en *security-only*) |
| Concurrencia | asyncio, un proceso por máquina | — |
| Validación y config | pydantic sobre `tomllib` para leer; `tomlkit` **para escribir** (enmendado, E-02) | pydantic ≥ 2.13 |
| HTTP / WebSocket | `httpx` async / `websockets` | httpx ≥ 0.28, websockets ≥ 16 |
| Persistencia | JSON atómico vía `platformdirs` para el **estado operativo**; SQLite (stdlib) para el **histórico** (enmendado, E-05) | — |
| UI escritorio | Tkinter (stdlib) + `pystray` para bandeja | — |
| UI terminal | Textual | ≥ 8.2 |
| Empaquetado | hatchling (wheel/PyPI) + PyInstaller (binarios) | — |
| Gestor de proyecto | `uv`, **con `uv.lock` versionado** | — |
| Calidad | ruff, mypy `strict`, pytest, bandit, pip-audit, gitleaks, semgrep, trivy, import-linter, jscpd (duplicación), lizard + flake8-cognitive-complexity (complejidad) | — |
| Contenedores | **Ninguno para el producto** — es un agente de escritorio. Permitidos en desarrollo y build (enmendado, E-03) | — |

**Regla de versiones:** todo rango de dependencia DEBERÁ llevar techo superior (`>=X,<Y`) y el
lockfile DEBERÁ estar versionado. *Racional: hoy hay saltos mayores entre rango declarado y
versión resuelta — `websockets` 12→16, `textual` 0.60→8.2 (`docs/code-audit/` §7).*
**Excepción nombrada (E-04):** `tzdata` queda exento del techo superior. Son datos de la IANA, no
una API: su versión mayor es el año de publicación, y fijarle techo congelaría las reglas horarias.

**Destinos de red (E-06, regla nueva):** los destinos externos a los que el agente se conecta
DEBERÁN estar declarados. Introducir uno nuevo exige enmienda. *Racional: hasta la v0.6.0 los
destinos eran los cuatro catálogos sísmicos; el mapa del histórico añade un proveedor de teselas,
y esa clase de decisión no debe entrar sin quedar registrada.*

---

## Enmiendas

Origen y argumento completo de cada una: [`docs/v1/00-ENMIENDAS-CONSTITUCION.md`](../../v1/00-ENMIENDAS-CONSTITUCION.md).

| Fecha | Artículo | Cambio | Razón | Aprobado por |
|---|---|---|---|---|
| 2026-09-06 | Ratificación | Ratificación inicial v1.0 | — | Mantenedor |
| 2026-09-19 | Stack · Lenguaje | Piso Python ≥ 3.12 → **≥ 3.13** (E-01) | 3.12 en *security-only*; ver `PAQUETERIA-VERSIONADO.md` §2 | Mantenedor (D-3) |
| 2026-09-19 | Stack · Config | Config de solo lectura → **escribible** con `tomlkit` (E-02) | Panel gráfico de configuración; enmienda ADR-007 | Mantenedor |
| 2026-09-19 | Stack · Contenedores | "Ninguno" → **ninguno para el producto**; permitidos en desarrollo y build (E-03) | Devcontainer (B-34) y build con glibc fijada (B-23) | Mantenedor |
| 2026-09-19 | Regla de versiones | Excepción nombrada: `tzdata` sin techo superior (E-04) | Son datos IANA, no una API | Mantenedor |
| 2026-09-19 | Stack · Persistencia | "Sin base de datos" → **solo para el estado operativo**; SQLite para el histórico (E-05) | El histórico exige consultas por rango que un JSON no da; SQLite es stdlib | Mantenedor |
| 2026-09-19 | Stack · Destinos de red *(regla nueva)* | Los destinos externos se declaran; uno nuevo exige enmienda (E-06) | El mapa introduce un proveedor de teselas | Mantenedor |

---

## Constitution check — cómo usarlo

Cada PRD, Technical Design y Plan cierra con 3-5 líneas: qué artículos aplican y cómo se cumplen,
o qué excepción se pide y por qué. **Una excepción sin justificación escrita es una violación** y
el Analyze la reporta como CRÍTICO.

Para que cada sesión de agente herede estos principios, `CLAUDE.md` debe apuntar a este archivo.
