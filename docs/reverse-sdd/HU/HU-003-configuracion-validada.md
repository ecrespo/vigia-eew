# HU-003: Configuración TOML validada y auto-sembrada

> **Cluster de origen:** Fase 1 + RF-24 · **Commits:** 2 `[COMMITS: b5c5371, a06f7a1]`
> **Período:** 2026-06-28 → 2026-07-05 · **Era:** Era 0 + Era 3

## Historia

**Como** usuario que instala el agente `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** encontrar un `config.toml` listo para editar y que los errores se detecten al arrancar
**Para** no descubrir que mi configuración estaba mal justo cuando ocurre un sismo

## Contexto de la implementación original

`load_config` `[VERIFY: src/vigia_eew/config.py:251]` lee con `tomllib` (stdlib 3.11+) y
valida con pydantic hacia `Settings` `[VERIFY: src/vigia_eew/config.py:142]`. Es
deliberadamente **pura**: no hace red ni I/O de estado; solo expone si `[reference]` estaba
presente `[VERIFY: src/vigia_eew/config.py:276]`, y quien resuelve la ubicación es
`Application` (HU-016). Esa frontera es lo que mantiene testeable el arranque.

`a06f7a1` añadió el sembrado desde plantilla empaquetada
`[VERIFY: src/vigia_eew/config.py:176]`: el usuario nuevo ya no parte de un archivo
inexistente.

## Criterios de aceptación

### CA-003.1: Sin archivo, se aplican valores por defecto válidos
```gherkin
Dado que no existe config.toml
Cuando se carga la configuración
Entonces se obtienen defaults válidos para todas las secciones
```
*Fuente: test `[VERIFY: tests/test_config.py:39]`*

### CA-003.2: Un archivo TOML válido sobrescribe los defaults
```gherkin
Dado un config.toml con secciones de fuentes y filtro
Cuando se carga
Entonces los valores del archivo prevalecen
```
*Fuente: tests `[VERIFY: tests/test_config.py:105]`, `[VERIFY: tests/test_config.py:61]`
(FUNVISIS), `[VERIFY: tests/test_config.py:78]` (GEOFON),
`[VERIFY: tests/test_config.py:88]` (país), `[VERIFY: tests/test_config.py:98]` (today_only)*

### CA-003.3: Una ruta explícita inexistente falla claramente
```gherkin
Dado --config apuntando a un archivo que no existe
Cuando se carga la configuración
Entonces falla con un error explícito, sin caer en defaults silenciosos
```
*Fuente: tests `[VERIFY: tests/test_config.py:117]`, `[VERIFY: tests/test_cli.py:88]`*

### CA-003.4: Umbrales de severidad incoherentes se rechazan
```gherkin
Dado un config con info_max mayor o igual que warning_max
Cuando se valida
Entonces la carga falla
```
*Fuente: test `[VERIFY: tests/test_config.py:122]` — un orden inválido rompería la
clasificación de severidad y con ella el color y el sonido de la alerta*

### CA-003.5: La plantilla empaquetada es TOML válido y trae `[reference]` comentado
```gherkin
Dado el config.toml.example incluido en el paquete
Cuando se parsea
Entonces es TOML válido y la sección [reference] está comentada
```
*Fuente: tests `[VERIFY: tests/test_config.py:127]`, `[VERIFY: tests/test_config.py:135]`
— si viniera descomentada, anularía la detección automática por IP de HU-016*

### CA-003.6: El primer arranque siembra el archivo sin sobrescribir uno existente
```gherkin
Dado que no existe config.toml en la ruta por defecto
Cuando arranca el agente sin --config
Entonces se crea desde la plantilla, incluyendo el directorio padre
Y si ya existía, no se toca
```
*Fuente: tests `[VERIFY: tests/test_config.py:142]`, `[VERIFY: tests/test_config.py:151]`,
`[VERIFY: tests/test_cli.py:116]`, `[VERIFY: tests/test_cli.py:122]`*

### CA-003.7: El sembrado es best-effort
```gherkin
Dado un error de sistema de archivos al sembrar
Cuando arranca el agente
Entonces se registra el problema y el agente continúa
```
*Fuente: test `[VERIFY: tests/test_config.py:167]`*

### CA-003.8: Se detecta si el usuario definió `[reference]` manualmente
```gherkin
Dado un config con o sin la sección [reference]
Cuando se consulta has_manual_reference
Entonces devuelve True o False correctamente
```
*Fuente: tests `[VERIFY: tests/test_config.py:180]`, `[VERIFY: tests/test_config.py:186]`,
`[VERIFY: tests/test_config.py:192]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-003.1 | CA-003.1 | feliz | Sin archivo | — | Defaults válidos | `[VERIFY: tests/test_config.py:39]` |
| TC-003.2 | CA-003.2 | feliz | TOML completo | secciones | Valores aplicados | `[VERIFY: tests/test_config.py:105]` |
| TC-003.3 | CA-003.3 | negativo | Ruta inexistente | `/no/existe.toml` | Error explícito | `[VERIFY: tests/test_config.py:117]` |
| TC-003.4 | CA-003.4 | negativo | Severidades invertidas | info_max>warning_max | ValidationError | `[VERIFY: tests/test_config.py:122]` |
| TC-003.5 | CA-003.5 | borde | Plantilla empaquetada | example | TOML válido, reference comentada | `[VERIFY: tests/test_config.py:135]` |
| TC-003.6 | CA-003.6 | feliz | Primer arranque | sin archivo | Creado desde plantilla | `[VERIFY: tests/test_config.py:142]` |
| TC-003.7 | CA-003.6 | borde | Ya existe | archivo previo | No se sobrescribe | `[VERIFY: tests/test_config.py:151]` |
| TC-003.8 | CA-003.7 | negativo | OSError al sembrar | permiso denegado | Continúa con log | `[VERIFY: tests/test_config.py:167]` |
| TC-003.9 | CA-003.8 | feliz | Con y sin `[reference]` | ambos | True / False | `[VERIFY: tests/test_config.py:180]` |
| TC-003.10 | CA-003.3 | borde | `--check-config` valida y sale sin construir la app | flag | Exit limpio | `[VERIFY: tests/test_cli.py:81]` |

## Dependencias

- **Requiere**: ninguna
- **Habilita**: todas las HU que leen configuración (HU-005…HU-022)

## Notas para la v2

La pureza de `load_config` (sin red ni estado) es la decisión a preservar: hace que el
arranque se pueda testear sin mocks de red. En la v2, mantener la validación como gate de
arranque y considerar exponer `--check-config` en CI del usuario.
