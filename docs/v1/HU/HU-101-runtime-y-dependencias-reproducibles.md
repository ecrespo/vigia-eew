# HU-101 · Resolución reproducible y runtime con soporte

> Épica **EP-1** · Prioridad **P0** · Esfuerzo ≈ 1 jornada · Fases **F0** y **F1**
> Ítems: B-01, B-02, B-03, B-04, B-05, B-13, B-16, B-17 · Requisitos: REQ-DEP-001..008

**Como** persona que instala Vigía-eew en su equipo,
**quiero** que la instalación resuelva exactamente las versiones que el proyecto verificó,
**para** no acabar ejecutando un árbol de dependencias distinto —y posiblemente vulnerable— del que
se probó.

## Contexto

Tres cosas ocurren hoy y las tres son invisibles para quien instala:

1. `uv.lock` está en `.gitignore:29`. Lo que protege al desarrollador **no viaja al usuario**.
2. `Pillow>=10.0` admite versiones con **34 avisos** conocidos. El lockfile resuelve 12.3.0, que
   tiene cero — pero el rango es lo único que el paquete publicado declara.
3. El piso es Python 3.11, en fase *security-only*: ya no recibe correcciones de errores.

**El orden importa y no es preferencia.** `requires-python` determina qué versiones son resolubles,
así que subir el runtime **antes** de fijar techos evita rehacerlos.

## Criterios de aceptación

```gherkin
Escenario: CA-101.1 · El lockfile viaja con el repositorio
  Dado un clon limpio del repositorio
  Cuando se ejecuta "uv sync --frozen"
  Entonces el entorno se instala sin resolver dependencias
  Y "git ls-files uv.lock" devuelve el archivo

Escenario: CA-101.2 · La caché de CI vuelve a depender del lockfile
  Dado que el lockfile está versionado
  Cuando se inspecciona la acción compuesta de preparación del entorno
  Entonces "cache-dependency-glob" apunta a uv.lock
  Y el comentario que declaraba el rodeo ha desaparecido

Escenario: CA-101.3 · El piso de un rango no admite versiones con avisos
  Dado el conjunto de dependencias de runtime
  Cuando se resuelve con la versión mínima que cada rango permite
  Entonces el árbol resultante no contiene ningún aviso de seguridad publicado

Escenario: CA-101.4 · Un piso rebajado hace fallar el pipeline
  Dado un rango cuyo piso se rebaja deliberadamente a una versión con avisos
  Cuando se ejecuta el pipeline de integración
  Entonces la ejecución falla nombrando el paquete y el aviso

Escenario: CA-101.5 · El runtime declarado recibe correcciones de errores
  Cuando se inspeccionan pyproject.toml, la configuración de ruff, la de mypy y los tres jobs de construcción
  Entonces los cinco declaran la misma versión de Python
  Y esa versión está en fase de correcciones de errores, no solo de seguridad

Escenario: CA-101.6 · La compatibilidad se verifica en dos versiones
  Cuando se ejecuta el pipeline de integración
  Entonces la suite completa se ejecuta en 3.13 y en 3.14
  Y ambas pasan

Escenario: CA-101.7 · Ningún salto de mayor ocurre sin decisión
  Dado que una dependencia publica una versión mayor nueva
  Cuando se vuelve a resolver el árbol sin cambiar los rangos declarados
  Entonces la versión mayor nueva no se adopta
  Y la excepción de tzdata está declarada por escrito en las enmiendas

Escenario: CA-101.8 · Las dependencias de macOS y Windows también se auditan
  Cuando se ejecuta la auditoría de composición
  Entonces cubre los 9 paquetes de runtime y los 6 específicos de plataforma
  Y cada plataforma se audita en su propio ejecutor
```

## Definición de hecho

- [ ] `uv sync --frozen` reproduce el entorno en una máquina limpia
- [ ] `uv sync --resolution lowest-direct` produce un árbol sin avisos
- [ ] La suite pasa en 3.13 y 3.14, y los tres jobs producen binario
- [ ] 8 de 9 rangos con techo superior; `tzdata` exento y documentado
- [ ] El informe de composición cubre 15 paquetes, no 9

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-DEP-001 | CA-101.1, CA-101.2 | B-01 | `.gitignore:29`; `setup-python-env/action.yml:16` |
| REQ-DEP-002 | CA-101.3 | B-02 | `PAQUETERIA-VERSIONADO.md` P-02 |
| REQ-DEP-003 | CA-101.3 | B-03 | SCA: CVE-2026-13346 en `pip` |
| REQ-DEP-004 | CA-101.5 | B-04 | `PAQUETERIA-VERSIONADO.md` P-01 |
| REQ-DEP-005 | CA-101.7 | B-05 | `PAQUETERIA-VERSIONADO.md` P-05 |
| REQ-DEP-006 | CA-101.4 | B-13 | Sin este gate, P-02 vuelve inadvertido |
| REQ-DEP-007 | CA-101.6 | B-16 | `ci.yml` no fija versión hoy |
| REQ-DEP-008 | CA-101.8 | B-17 | Hueco declarado del SCA |

**Bloqueo:** CA-101.5 depende de la decisión **D-3** y de la enmienda
[E-01](../00-ENMIENDAS-CONSTITUCION.md).
