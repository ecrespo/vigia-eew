# ADR-020: Obligar las fronteras con import-linter en el gate

> **Estado**: propuesto · **Fecha**: 2026-08-16 · **Debilidad que ataca**: DEB-02
> **Numeración**: continúa la serie de `docs/TECHNICAL-DESIGN.md`, que llega hasta ADR-018.

## Contexto

La dirección de dependencias del proyecto es correcta y verificada: el dominio no importa
infraestructura, no hay ciclos, y `pipeline/` solo depende del núcleo. Es **la propiedad
que hace posible el 89 % de cobertura** — si `pipeline/filter.py` importara `httpx`, no
habría forma de testear el filtro sin red.

Esa propiedad no tiene ninguna red de seguridad. `[VERIFY: .pre-commit-config.yaml]` y
`[VERIFY: pyproject.toml]`: el gate corre ruff, mypy strict, bandit, pytest, pip-audit,
semgrep y trivy — **ninguno mira la dirección de los imports**. Una regresión aquí pasaría
los 345 tests sin levantar una sola alarma.

## Decisión

Añadir `import-linter` con tres contratos y ejecutarlo en el gate rápido de pre-commit,
junto a ruff y mypy:

1. **Capas**: `frontends` (`app`, `cli`, `tray`, `tui`) → `adaptadores` (`ingest`,
   `notify`, `autostart`) → `dominio` (`pipeline`) → `núcleo` (`core`). Ninguna capa puede
   importar hacia arriba.
2. **Núcleo independiente**: `core` no puede importar **nada** del propio paquete.
3. **Dominio sin infraestructura**: `pipeline` y `core` no pueden importar `httpx`,
   `websockets`, `tkinter`, `pystray`, `textual` ni `subprocess`.

El contrato 3 es el que más importa y **se puede adoptar hoy mismo, sin ADR-019**: no
depende de mover ningún archivo.

## Alternativas consideradas

### Alternativa A: import-linter en pre-commit (la propuesta)

- **Ventajas**: declarativo, sin dependencias pesadas, corre en menos de un segundo. Falla
  en el commit, que es donde el coste de corregir es mínimo. Convierte la arquitectura en
  algo ejecutable en vez de documentado — y este repo ya documenta bien, así que lo que
  falta es precisamente la verificación.
- **Desventajas**: una dependencia de desarrollo más, y un archivo de contratos que hay que
  actualizar cuando la arquitectura cambie a propósito (fricción deseable, pero fricción).
- **Costo**: ~2 horas, incluyendo escribir los contratos y verificar que el estado actual
  ya pasa.

### Alternativa B: un test de arquitectura en pytest

Un test que recorra el AST y afirme las mismas reglas — el repo ya tiene el hábito de
verificar cosas con tests, y este informe usó exactamente esa técnica para descartar el
ciclo falso.

- **Ventajas**: cero dependencias nuevas, corre con el suite que ya existe, y el patrón
  encaja con la cultura del repo.
- **Desventajas**: hay que escribir y mantener el recorrido del AST (~60 líneas) en vez de
  declarar contratos; los mensajes de error son los que uno se moleste en escribir, frente
  a los de import-linter que ya señalan la cadena de imports culpable. Es reinventar una
  rueda pequeña pero real.
- **Costo**: ~3 horas y mantenimiento propio a futuro.

### Alternativa C: no hacer nada

- **Qué cuesta convivir con el problema**: con un solo autor que diseñó estas fronteras a
  propósito y las documentó en 18 ADRs, la probabilidad de una regresión accidental es
  **genuinamente baja**. En 49 commits no ha ocurrido ni una vez — la evidencia empírica
  favorece esta alternativa más de lo que resulta cómodo admitir.
- **Cuándo sería razonable elegirla**: si el proyecto seguirá siendo de un autor. El
  argumento en contra no es el riesgo de hoy, es la asimetría: el coste de la regla son 2
  horas una vez, y el coste de descubrir la erosión arquitectónica tarde es un refactor.
  Además, este repo **ya paga** por esa clase de seguro en todas las demás dimensiones
  (mypy strict, bandit, gitleaks, trivy). No cubrir la arquitectura es la excepción, no la
  norma del proyecto.

## Consecuencias

- **Positivas**: la fortaleza #1 pasa de convención a invariante verificada. `[METRIC]`
  verificable: `lint-imports` en verde con 3 contratos. Un contribuidor externo recibe el
  error en el commit, no en la revisión.
- **Negativas**: un cambio arquitectónico legítimo ahora exige también actualizar los
  contratos. Es fricción intencional, pero es fricción real y a veces molesta.
- **Neutrales**: `import-linter` entra en el grupo `dev` de `pyproject.toml`; no afecta al
  runtime ni al paquete distribuido.

## Reversibilidad

**Trivialmente reversible**: borrar el archivo de contratos y el hook. No toca código de
producción en absoluto.

## Guardas anti-sobreingeniería

- [x] **No introduce capas nuevas**: describe las que ya existen. Si un contrato no pasa
      con el código actual, la respuesta correcta es corregir el contrato, no el código —
      señal de que la capa que describí no era la real.
- [x] **No extrae servicios**: nada distribuido.
- [x] **Existe una versión más aburrida y se explicó**: adoptar **solo el contrato 3**
      (dominio sin infraestructura), que es una regla de 4 líneas, no depende de ADR-019 y
      captura el riesgo que de verdad importa. Si hay que elegir uno, es ese.
- [x] **Declara qué NO se toca**: ningún archivo de `src/` cambia. Si el estado actual no
      pasara algún contrato, este ADR **no** autoriza a mover código para satisfacerlo: eso
      sería otra decisión, con su propio ADR.
