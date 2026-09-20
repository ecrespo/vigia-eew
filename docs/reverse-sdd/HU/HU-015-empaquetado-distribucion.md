# HU-015: Empaquetado y distribución multiplataforma

> **Cluster de origen:** Fase 8 + fixes de artefacto · **Commits:** 5
> `[COMMITS: b6413e3, 7b1c71c, c38d9f6, bdc2a9d, a02607f]`
> **Período:** 2026-07-03 → 2026-07-04 · **Era:** Era 0 + Era 1 + Era 2

## Historia

**Como** usuario sin entorno de desarrollo Python `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** instalar el agente desde un paquete nativo de mi sistema
**Para** usarlo sin saber qué es un virtualenv

## Contexto de la implementación original

`build.yml` produce wheel+sdist, `.exe` de Windows, `.dmg` de macOS y AppImage + `.deb`
/`.rpm` de Linux, cada uno en su runner nativo
`[VERIFY: .github/workflows/build.yml:21]`, y publica a PyPI tras construir todo
`[VERIFY: .github/workflows/build.yml:93]`. Los scripts por plataforma viven en
`packaging/` `[VERIFY: packaging/vigia-eew.spec:40]`.

**Esta es la HU con más fixes del historial, y ninguno fue de lógica de negocio.** El
código estaba probado; el artefacto no. Los cuatro fixes son la mejor fuente de criterios
de aceptación del kit, porque cada uno describe una forma real en que la distribución se
rompió en producción.

## Criterios de aceptación

### CA-015.1: Se generan artefactos para las tres plataformas
```gherkin
Dado un tag de versión vX.Y.Z
Cuando corre el workflow de build
Entonces se producen wheel+sdist, .exe, .dmg y AppImage/.deb/.rpm
```
*Fuente: código `[VERIFY: .github/workflows/build.yml:21]`*

### CA-015.2: La publicación a PyPI ocurre solo tras construir todo
```gherkin
Dado que alguno de los builds de plataforma falla
Cuando termina el workflow
Entonces no se publica a PyPI
```
*Fuente: código `[VERIFY: .github/workflows/build.yml:93]`, fix `[COMMITS: 5ee3b1d]` —
evita publicar una versión en PyPI cuyos binarios nativos no existen*

### CA-015.3: Los iconos empaquetados tienen resolución válida
```gherkin
Dado los assets de icono usados por el empaquetado Linux
Cuando corren linuxdeploy y appimagetool
Entonces aceptan el icono y el build termina
```
*Fuente: fixes `[COMMITS: 7b1c71c]` (AppImage) y `[COMMITS: c38d9f6]` (linuxdeploy) — un
icono placeholder con resolución inválida rompió el build **dos releases seguidas**;
ningún test lo habría detectado porque el fallo estaba en el artefacto, no en el código*

### CA-015.4: Los recursos dinámicos de las dependencias se incluyen en el binario
```gherkin
Dado que desktop_notifier accede a sus recursos vía importlib.resources
Cuando se construye el binario PyInstaller
Entonces desktop_notifier.resources se incluye explícitamente como hiddenimport
```
*Fuente: fix `[COMMITS: bdc2a9d]`, código `[VERIFY: packaging/vigia-eew.spec:50]` — las
referencias dinámicas son invisibles al análisis estático de PyInstaller, y el fallo
solo aparece en el binario, nunca en desarrollo*

### CA-015.5: Los binarios del sistema se lanzan con entorno saneado
```gherkin
Dado un bundle onefile de PyInstaller
Cuando el agente lanza un binario del sistema
Entonces LD_LIBRARY_PATH y DYLD_LIBRARY_PATH se restauran o se eliminan
```
*Fuente: fix `[COMMITS: a02607f]`, tests
`[VERIFY: tests/test_subprocess_env.py:23]`, `[VERIFY: tests/test_subprocess_env.py:32]`,
`[VERIFY: tests/test_subprocess_env.py:42]` — sin esto, el reproductor de sonido carga
las librerías del bundle en vez de las del sistema y falla de una forma que parece un bug
de la funcionalidad*

### CA-015.6: Sin bundle congelado, el entorno no se altera
```gherkin
Dado una ejecución normal (no congelada)
Cuando se pide el entorno para subprocesos
Entonces no se aplica saneamiento
```
*Fuente: test `[VERIFY: tests/test_subprocess_env.py:18]`*

### CA-015.7: El entorno devuelto es una copia
```gherkin
Dado la construcción del entorno saneado
Cuando se modifica el resultado
Entonces os.environ del proceso no se ve afectado
```
*Fuente: test `[VERIFY: tests/test_subprocess_env.py:61]`*

### CA-015.8: Los assets del paquete se incluyen y se resuelven en runtime
```gherkin
Dado los WAV de severidad, el icono de bandeja y countries.geojson
Cuando corre el binario empaquetado
Entonces las rutas de asset se resuelven correctamente
```
*Fuente: código `[VERIFY: packaging/vigia-eew.spec:40]`, tests
`[VERIFY: tests/test_sound.py:56]`, `[VERIFY: tests/test_tray.py:77]`,
`[VERIFY: tests/test_geocode.py:69]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-015.1 | CA-015.1 | feliz | Build por tag | v0.6.0 | 4 familias de artefacto | CI, sin test unitario |
| TC-015.2 | CA-015.2 | negativo | Un build falla | .dmg falla | No publica a PyPI | CI |
| TC-015.3 | CA-015.3 | negativo | Icono inválido | resolución mala | Build falla temprano con mensaje claro | **escribir en v2** |
| TC-015.4 | CA-015.4 | negativo | Recurso dinámico ausente | sin hiddenimport | ModuleNotFoundError al arrancar el binario | **escribir en v2** |
| TC-015.5 | CA-015.5 | borde | Frozen sin ORIG | LD_LIBRARY_PATH puesto | Se elimina | `[VERIFY: tests/test_subprocess_env.py:23]` |
| TC-015.6 | CA-015.5 | borde | Frozen con ORIG | valor original | Se restaura | `[VERIFY: tests/test_subprocess_env.py:32]` |
| TC-015.7 | CA-015.5 | borde | macOS DYLD | DYLD_LIBRARY_PATH | Se elimina | `[VERIFY: tests/test_subprocess_env.py:42]` |
| TC-015.8 | CA-015.6 | feliz | No congelado | normal | Sin cambios | `[VERIFY: tests/test_subprocess_env.py:18]` |
| TC-015.9 | CA-015.7 | borde | Copia del entorno | mutación | os.environ intacto | `[VERIFY: tests/test_subprocess_env.py:61]` |
| TC-015.10 | CA-015.8 | feliz | Assets empaquetados | binario | Rutas resueltas | `[VERIFY: tests/test_geocode.py:69]` |
| TC-015.11 | CA-015.1 | borde | **Humo del artefacto**: el binario arranca y `--simulate` muestra la alerta | .exe/.dmg/AppImage recién construidos | Alerta visible | **escribir en v2** |

## Dependencias

- **Requiere**: HU-013 (el CLI empaquetado)
- **Habilita**: HU-014 (autoarranque del binario congelado)

## Notas para la v2

**Lección número uno del historial completo** (ver `03-EVOLUCION.md`, Era 1): tres
releases de parche consecutivas por fallos de empaquetado. TC-015.3, TC-015.4 y sobre
todo TC-015.11 son los tests que no existen y que habrían evitado las tres.

TC-015.11 —arrancar el artefacto construido y correr `--simulate` como paso de CI— es la
recomendación más accionable de todo el kit: cubre de una vez el icono, los recursos
dinámicos, las rutas de asset y el saneamiento de entorno, que son exactamente los cuatro
fixes de esta HU. En la v2, el empaquetado debe existir desde la fase 1 y no desde la
fase 8.
