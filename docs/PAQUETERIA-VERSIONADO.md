# Paquetería y versionado — Vigía-eew

> Fecha del análisis: **2026-09-06** · Commit: `c3a2c29` (v0.6.0)
> Combina la evidencia SCA ya generada en `docs/code-audit/analysis/sca-pypi-advisory.txt` con
> consulta a los calendarios oficiales de fin de soporte y al índice de PyPI.

## 0. Aviso sobre severidades

**La herramienta SCA utilizada no reporta severidad.** El feed de avisos de PyPI
(`https://pypi.org/pypi/<pkg>/<ver>/json`, la misma fuente que `pip-audit -s pypi`) expone
únicamente estos campos por aviso: `id`, `aliases`, `summary`, `details`, `fixed_in`, `link`,
`source`, `withdrawn`. **No incluye CVSS ni etiqueta de severidad.**

En consecuencia, este documento reporta **número de avisos**, no severidades, salvo en el único
caso donde una fuente pública sí publica una puntuación: se cita con su origen y se marca como
externa a la herramienta. **Ninguna severidad de esta tabla está estimada.**

---

## 1. Semáforo

| Ámbito | Estado | Motivo |
|---|---|---|
| **Runtime (Python)** | 🟡 | El piso declarado (3.11) está en **fase security-only** desde hace dos años; 3.12 también |
| **Vulnerabilidades en versiones instaladas** | 🟢 | 89 de 90 paquetes del lockfile sin avisos; el único afectado es `pip`, dependencia de desarrollo |
| **Rangos declarados** | 🔴 | `Pillow>=10.0` **permite instalar versiones con 34 avisos conocidos** |
| **Mantenimiento de dependencias** | 🟡 | `pystray` sin publicar desde hace **1.085 días**; `httpx` estable sin release desde hace 639 días |
| **Reproducibilidad** | 🔴 | `uv.lock` **no está versionado**: lo que protege hoy al desarrollador no protege al usuario final |

---

## 2. Runtime: Python

Piso declarado en el proyecto: `requires-python = ">=3.11"`; `mypy` y `ruff` apuntan a `py311`.

| Versión | Estado | Primera release | Fin de soporte | Situación para este proyecto |
|---|---|---|---|---|
| 3.10 | security-only | 2021-10-04 | **2026-10** | Fuera del piso del proyecto. **EOL el mes que viene** |
| **3.11** | **security-only** | 2022-10-24 | 2027-10 | **Piso actual del proyecto.** Ya no recibe correcciones de errores, solo de seguridad |
| **3.12** | **security-only** | 2023-10-02 | 2028-10 | Piso propuesto por la constitución de la v2 — **también en security-only** |
| 3.13 | bugfix | 2024-10-07 | 2029-10 | **Piso recomendado para la v2** |
| 3.14 | bugfix | 2025-10-07 | 2030-10 | Alternativa; soporte completo más largo |
| 3.15 | prerelease | *2026-10-01* | *2031-10* | Aún no publicada |

Desde 3.13 la fase de correcciones de errores dura **dos años** (antes 18 meses), seguida de tres
de solo seguridad; el total sigue siendo cinco años.

### 🔴 Hallazgo P-01 — El piso de la v2 aterriza en una versión ya en security-only

La constitución de la v2 fija **Python ≥ 3.12** (`docs/sdd/specs/00-CONSTITUTION.md`, restricciones
de stack). Contrastado con el calendario oficial: **la guía oficial marca 3.12 como `security`** — fase
iniciada hacia abril de 2025, derivado de la regla de 18 meses de correcciones que la propia
política documenta. Una v2 que empieza hoy nacería sobre una versión que ya no recibe correcciones de errores,
solo parches de seguridad, y con solo dos años de vida restante.

**Recomendación: subir el piso de la v2 a Python ≥ 3.13**, que está en fase *bugfix* hasta
octubre de 2027 y con soporte hasta octubre de 2029. El coste es nulo: la única razón del piso 3.11
era `tomllib`, disponible desde entonces.

> Esta es una **corrección al documento que yo mismo generé en el paso anterior**. Se deja anotada
> aquí en lugar de editar la constitución en silencio, porque cambiar una restricción de stack de
> la constitución exige una enmienda con changelog (su propia sección de Enmiendas lo establece).

---

## 3. Paquetería principal — dependencias de runtime

Las nueve que se instalan con el paquete y viajan al usuario final.

| Paquete | Rango declarado | En `uv.lock` | Última en PyPI | Última publicación | Avisos en la versión del lock | Avisos en el **mínimo que el rango permite** | Estado |
|---|---|---|---|---|---|---|---|
| `websockets` | `>=12.0` | 16.0 | **17.1** | 2026-08-26 | 0 | 0 (en 12.0) | 🟡 rango admite 5 mayores por encima |
| `httpx` | `>=0.27` | 0.28.1 | 0.28.1 | **2024-12-06** | 0 | 0 (en 0.27) | 🟡 sin release estable en 639 días |
| `pydantic` | `>=2.6` | 2.13.4 | 2.13.5 | 2026-08-28 | 0 | 0 (en 2.6) | 🟢 activo |
| `desktop-notifier` | `>=5.0` | 6.2.0 | 6.2.0 | 2025-08-08 | 0 | 0 (en 5.0) | 🟡 394 días sin release |
| `platformdirs` | `>=4.0` | 4.10.0 | 4.11.7 | 2026-09-01 | 0 | 0 (en 4.0) | 🟢 muy activo |
| `tzdata` | `>=2024.1` | 2026.2 | 2026.3 | 2026-07-10 | 0 | 0 | 🟢 activo (datos IANA) |
| `pystray` | `>=0.19` | 0.19.5 | 0.19.5 | **2023-09-17** | 0 | 0 (en 0.19) | 🔴 **1.085 días sin release** |
| **`Pillow`** | **`>=10.0`** | **12.3.0** | 12.3.0 | 2026-07-01 | **0** | **34** | 🔴 **el rango permite versiones vulnerables** |
| `textual` | `>=0.60` | 8.2.8 | 8.2.8 | 2026-06-30 | 0 | 0 (en 0.60) | 🟢 activo |

### 🔴 Hallazgo P-02 — `Pillow>=10.0` permite instalar 34 avisos conocidos

El lockfile resuelve Pillow **12.3.0, que no tiene ningún aviso**. Pero el rango declarado en
`pyproject.toml` admite cualquier versión desde la 10.0, y la progresión es contundente:

| Versión de Pillow | Avisos en el feed de PyPI |
|---|---|
| 10.0.0 | **34** |
| 11.0.0 | 33 |
| 11.2.1 | **37** |
| 12.0.0 | 37 |
| 12.1.0 | 37 |
| 12.2.0 | 25 |
| **12.3.0** | **0** ← piso de seguridad real |

Pillow es el analizador de formatos de imagen del proyecto (lo exige `pystray` para el ícono de
bandeja) y es históricamente una de las superficies de ataque más activas del ecosistema Python.

**Por qué esto importa más de lo que parece:** un `pip install vigia-eew` hoy resuelve la más
reciente y queda a salvo. Pero el rango es lo único que el paquete publicado declara, y el
`uv.lock` **no está versionado** (`docs/code-audit/` §7). Cualquier entorno con caché antigua,
resolución restringida por otra dependencia, o una imagen base con Pillow preinstalada, satisface
el rango declarado arrastrando decenas de avisos.

**Acción:** `Pillow>=12.3.0,<13` — el piso pasa a ser el piso de seguridad real.

### 🟡 Hallazgo P-03 — `pystray` lleva casi tres años sin publicar

Última versión en PyPI: **0.19.5, del 17 de septiembre de 2023** — 1.085 días al momento de este
análisis. Es la única dependencia de runtime en esa situación, y arrastra dos consecuencias que ya
estaban documentadas por separado y que aquí se juntan:

1. Es quien **obliga a incluir Pillow** (`Icon(icon=PIL.Image)`), es decir, quien introduce el
   hallazgo P-02 en el árbol de dependencias.
2. Las dos limitaciones conocidas de la bandeja — GNOME/Wayland sin extensión AppIndicator, y el
   conflicto de Cocoa con Tkinter en macOS — **no tienen a quién reportarse con expectativa de
   arreglo**. El repositorio del proyecto tiene abierta desde hace tiempo la incidencia
   *"So .... how to support Wayland?"*.

**Contexto atenuante, y por eso es 🟡 y no 🔴:** la bandeja es *best-effort* por diseño (Art. 3 de
la constitución). Si falla, el agente arranca igual y solo pierde el ícono. Ninguna garantía del
producto depende de ella.

**Opciones para la v2**, en orden de coste: (a) mantener `pystray` y aceptar el riesgo por escrito;
(b) evaluar `tray_manager`, envoltorio activo sobre el mismo pystray — no resuelve el fondo;
(c) prescindir de la bandeja en Linux/Wayland y exponer el estado por el modo terminal, que ya
existe y sí cumple la garantía de alerta.

### 🟡 Hallazgo P-04 — `httpx` sigue en 0.x tras 639 días sin release estable

`httpx 0.28.1` es simultáneamente la versión del lockfile y **la última estable publicada**, del
6 de diciembre de 2024. La rama 1.0 lleva tiempo en pre-release. Además, el 27 de febrero de 2026
el mantenedor cerró incidencias y discusiones en el repositorio, lo que limita la vía habitual para
reportar y seguir un fallo.

Sin avisos de seguridad y con el cliente HTTP ejerciéndose de forma sencilla (GET con timeout), el
riesgo operativo hoy es bajo. Se registra como señal de mantenimiento a vigilar, no como defecto.

### 🟡 Hallazgo P-05 — Rangos sin techo superior sobre proyectos que sí rompen

`websockets>=12.0` con la última en **17.1**: **cinco versiones mayores** publicadas por encima
del piso declarado. `textual>=0.60` frente a 8.2.8: **ocho**. `pydantic>=2.6` frente a 2.13.5:
**siete versiones menores**.

Un `pip install` en una máquina limpia resuelve la más reciente, que puede haber cambiado su API
respecto a lo que el código espera. El lockfile lo evita en desarrollo, pero **no está versionado**,
así que la reproducibilidad depende de un archivo que no viaja con el repositorio.

Esto ya está recogido como riesgo en `docs/reverse-sdd/02-STACK-TECNOLOGICO.md` §7 y como regla en
la constitución de la v2; aquí se cuantifica el margen exacto.

---

## 4. Paquetería de desarrollo, seguridad y empaquetado

No viaja al usuario final. Se audita porque compromete al entorno de desarrollo y a los runners de CI.

| Paquete | Extra | Rango | En `uv.lock` | Última en PyPI | Última publicación | Avisos | Estado |
|---|---|---|---|---|---|---|---|
| `pytest` | dev | `>=8.0` | 9.1.1 | 9.1.1 | 2026-06-19 | 0 | 🟢 |
| `pytest-asyncio` | dev | `>=0.23` | 1.4.0 | 1.4.0 | 2026-05-26 | 0 | 🟢 |
| `pytest-cov` | dev | `>=5.0` | 7.1.0 | 7.1.0 | 2026-03-21 | 0 | 🟢 |
| `ruff` | dev | `>=0.5` | 0.15.20 | 0.16.6 | 2026-09-03 | 0 | 🟢 muy activo |
| `mypy` | dev | `>=1.10` | 2.1.0 | 2.3.1 | 2026-08-15 | 0 | 🟢 |
| `pre-commit` | dev | `>=3.7` | 4.6.0 | 4.6.2 | 2026-08-10 | 0 | 🟢 |
| `bandit` | security | `>=1.8` | 1.9.4 | 1.9.4 | 2026-02-25 | 0 | 🟢 |
| `pip-audit` | security | `>=2.7` | 2.10.1 | 2.10.1 | 2026-06-10 | 0 | 🟢 |
| `pyinstaller` | packaging | `>=6.0` | 6.21.0 | 6.22.2 | 2026-08-17 | 0 | 🟢 |
| **`pip`** | transitiva | — | **26.1.2** | 26.2.1 | 2026-08-04 | **2** | 🟡 ver P-06 |

### 🟡 Hallazgo P-06 — CVE-2026-13346 en `pip 26.1.2`

Único paquete con avisos de los 90 del lockfile, ya detectado en el paso 4.

| Dato | Valor | Fuente |
|---|---|---|
| Identificadores | `PYSEC-2026-3721` y `GHSA-qwm4-qh6w-59xr`, ambos alias de **CVE-2026-13346** | feed de avisos de PyPI |
| Descripción | pip manejaba incorrectamente URLs de paquete doblemente codificadas desde un índice, permitiendo instalar archivos en rutas arbitrarias del disco, incluso instalando wheels | feed de avisos de PyPI |
| Corregido en | **26.2** | feed de avisos de PyPI |
| Severidad | **CVSS 6.5** | ⚠️ **externa a la herramienta**: publicada por avisos de terceros; el feed de PyPI no reporta severidad |
| Cadena de dependencia | `pip` ← `pip-api` ← `pip-audit` (extra `security`) | `uv.lock` |
| Explotabilidad en este proyecto | Requiere instalar desde un **índice malicioso**. El proyecto solo usa PyPI oficial | análisis propio |

**No llega al usuario final**: no es dependencia de runtime, no viaja en el wheel ni en los binarios
de PyInstaller. Afecta al entorno de desarrollo y a los runners de CI.

**Acción:** `uv lock --upgrade-package pip` hasta ≥ 26.2. Ya está registrado como R-05 en
`docs/code-audit/02-PLAN-REMEDIACION.md`.

---

## 5. Inconsistencias con reportes previos

Documentadas aquí en lugar de corregirse en silencio, porque tocar esos documentos queda fuera del
alcance de esta tarea.

| # | Documento | Dice | Realidad verificada | Gravedad |
|---|---|---|---|---|
| I-01 | `docs/reverse-sdd/02-STACK-TECNOLOGICO.md` §7, última línea | *"Nada del stack está EOL. Python 3.11 sigue soportado; el mínimo podría subirse a 3.12 en la v2 sin coste"* | **Correcto pero incompleto.** 3.11 no está EOL, pero la guía oficial lo marca **security-only** (fase iniciada hacia abril de 2024, derivado de la regla de 18 meses de la propia política); 3.12 está igual desde ~abril de 2025. Recomendar 3.12 lleva a una versión igual de avanzada en su ciclo | **Media** — la conclusión práctica cambia: el destino correcto es 3.13 |
| I-02 | `docs/sdd/specs/00-CONSTITUTION.md`, restricciones de stack | Python **≥ 3.12** | Ver hallazgo P-01. Requiere enmienda formal, no edición | **Media** |
| I-03 | `docs/code-audit/01-INFORME-AUDITORIA.md` §7, tabla de riesgos | *"Deriva mayor entre rango y lockfile"* señalada correctamente como **Alta** | Confirmado y cuantificado: `websockets` admite 5 versiones mayores por encima del piso (13→17), `textual` 8 (1→8), `pydantic` 7 menores (2.7→2.13) | — coincide |
| I-04 | `docs/code-audit/01-INFORME-AUDITORIA.md`, dimensión 6 (SCA) | **🟢 verde**, "90/90 paquetes auditados, 1 con vulnerabilidad" | **Exacto**, verificado de nuevo hoy. Pero el veredicto verde evalúa las **versiones instaladas**, no los **rangos declarados**, y por ahí entra P-02 | **Baja** — no es un error; es un alcance que conviene explicitar |
| I-05 | Tabla de versiones de `docs/reverse-sdd/02-STACK-TECNOLOGICO.md` §3 y §6 | 16 versiones registradas | **16 de 16 coinciden** con `uv.lock`, contrastadas una a una | — sin discrepancias |

**Sobre I-04**, que es el matiz más útil: ningún informe previo estaba equivocado. La auditoría SCA
respondía "¿lo que está instalado tiene vulnerabilidades?" y la respuesta era, y sigue siendo, casi
un no rotundo. Este documento hace una pregunta distinta — "¿qué permite instalar lo que
declaramos?" — y ahí aparece P-02. Son dos preguntas, dos alcances, dos respuestas.

---

## 6. Acciones recomendadas

| # | Acción | Esfuerzo | Verificación |
|---|---|---|---|
| A-1 | `Pillow>=12.3.0,<13` en `pyproject.toml` | S | `pip install 'vigia-eew'` en entorno limpio → Pillow ≥ 12.3.0 |
| A-2 | **Versionar `uv.lock`** | S | El lockfile deja de estar en `.gitignore`; la CI cachea por él |
| A-3 | Techo superior en los nueve rangos de runtime (`>=X,<X+1`) | S | Un `uv lock` no puede saltar de versión mayor sin cambio explícito |
| A-4 | `uv lock --upgrade-package pip` → ≥ 26.2 | S | `pip-audit` sin `CVE-2026-13346` |
| A-5 | **Enmendar la constitución: Python ≥ 3.13** en vez de ≥ 3.12 | S | Fila de enmiendas con fecha y razón |
| A-6 | Decidir por escrito la política sobre `pystray`: mantener con riesgo aceptado, o retirar la bandeja donde no funciona | M | Nota en `lat.md/notification.md` |
| A-7 | Añadir a la CI un chequeo del **piso** de los rangos, no solo de lo instalado (`pip install` con `--resolution lowest` y auditar) | M | El gate detectaría hoy el hallazgo P-02 |

A-7 es la que convierte este análisis en permanente: sin ella, P-02 se vuelve a colar el día que se
añada una dependencia con rango abierto.

---

## 7. Método y trazabilidad

| Dato | Cómo se obtuvo |
|---|---|
| Versiones resueltas | `uv.lock` del repositorio, parseado directamente |
| Rangos declarados | `pyproject.toml`, secciones `dependencies` y `optional-dependencies` |
| Avisos por versión | Feed de avisos de PyPI, `https://pypi.org/pypi/<pkg>/<ver>/json` — la misma fuente que `pip-audit -s pypi`; consultada para 90 paquetes en el paso 4 y re-verificada hoy para los 19 principales |
| Fechas de publicación y última versión | API JSON de PyPI, campo `upload_time_iso_8601` |
| Calendario de Python | Guía oficial del desarrollador de Python (actualizada el 2026-05-27) |
| Severidad de CVE-2026-13346 | Avisos públicos de terceros — **no** de la herramienta SCA |
| Estado de mantenimiento | Fecha de la última publicación en PyPI, calculada; contrastada con búsqueda web |

**Limitación heredada del paso 4, aún vigente:** `api.osv.dev` responde 403 en el entorno de
análisis, así que la fuente de avisos es la base de PyPI en lugar de OSV. Para paquetes de PyPI la
cobertura es equivalente; OSV añadiría avisos de fuentes ajenas al índice.

**Seis paquetes del lockfile no se auditaron** por ser exclusivos de macOS o Windows y no
instalables en el entorno de análisis: `pyobjc-core`, `pyobjc-framework-cocoa`,
`pyobjc-framework-quartz`, `rubicon-objc`, `pywin32-ctypes`, `colorama`. Están en
`docs/code-audit/analysis/deps-omitidas-plataforma.txt`. Es un hueco real, pequeño y declarado.

---

## Fuentes

- [Status of Python versions — Python Developer's Guide](https://devguide.python.org/versions/)
- [Python End-of-Life Dates — endoflife.ai](https://endoflife.ai/article-python-eol)
- [pip Changelog — pip documentation](https://pip.pypa.io/en/latest/news/)
- [SUSE advisory: python-pip improper URL handling (CVE-2026-13346)](https://linuxsecurity.com/advisories/suse/suse-2026-23319-1-moderate-for-python-pip)
- [pystray · PyPI](https://pypi.org/project/pystray/)
- [pystray issue #174 — "So .... how to support Wayland?"](https://github.com/moses-palmer/pystray/issues/174)
- [pystray — Python Package Health Analysis, Snyk](https://snyk.io/advisor/python/pystray)
- [httpx · PyPI](https://pypi.org/project/httpx/) · [Releases · encode/httpx](https://github.com/encode/httpx/releases)
- [HTTPX Python Library Status in 2026](https://docs.bswen.com/blog/2026-03-05-httpx-library-status/)
- [Pillow PDF Parsing Trailer Infinite Loop (CVE-2026-42310) — GitHub Advisory Database](https://github.com/advisories/ghsa-r73j-pqj5-w3x7)
- [CVE-2026-42309: Pillow buffer overflow](https://www.sentinelone.com/vulnerability-database/cve-2026-42309/)
- [CVE-2026-59203: Pillow DoS](https://www.sentinelone.com/vulnerability-database/cve-2026-59203/)
