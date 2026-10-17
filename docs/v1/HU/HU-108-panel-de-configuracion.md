# HU-108 · Configurar sin editar un archivo

> Épica **EP-8** · Prioridad **P2** · Esfuerzo L · Fase **F5**
> Ítems: B-35, B-36 (en alcance) · B-37, B-38 (especificados, fuera del corte)
> Requisitos: REQ-CFG-009..012, REQ-GUI-001..007

**Como** usuario no técnico —que es el destinatario del producto—,
**quiero** ajustar mi ubicación, mi radio y mi magnitud mínima desde una interfaz,
**para** no tener que abrir un archivo de texto y aprender su sintaxis para saber si un sismo me
afecta.

## Contexto

Hoy la única vía es el menú de bandeja *"Editar configuración…"*, que abre `config.toml` con el
editor del sistema `[VERIFY: src/vigia_eew/tray.py:52]`. Funciona, está documentada y el archivo se
siembra solo en el primer arranque — pero pide al usuario exactamente lo que el producto intenta
evitarle.

**La superficie son 39 campos en 10 secciones**: referencia, filtro, cuatro fuentes, deduplicación,
severidad, notificación y registro. No es un diálogo de tres casillas, y por eso la HU pide
secciones plegables en lugar de una lista plana.

> El backlog §4 dice *"51 campos"*. El recuento sobre `src/vigia_eew/config.py` da **39 campos hoja**
> en 10 secciones. Las 10 secciones son correctas; la cifra de campos no se reproduce. Registrado
> como [V-02](../08-ANALYZE.md).

### El obstáculo va primero, y no es negociable

**La configuración es de solo lectura por decisión explícita.** ADR-007 eligió `tomllib` —el lector
de la biblioteca estándar, que no tiene escritor— y dejó anotada la consecuencia: *"writing config
isn't needed in v1"*. Un panel que guarda **contradice esa decisión vigente**.

Por eso **B-35** —la enmienda [E-02](../00-ENMIENDAS-CONSTITUCION.md) y el ADR que la sostiene— es
requisito previo. Escribir el panel antes sería construir sobre una decisión que dice lo contrario.

### El riesgo propio de esta épica

Es **el primer componente que escribe** en un archivo que el usuario también edita a mano. Si
alguien lo tiene abierto en su editor mientras el panel guarda, uno de los dos pierde el trabajo.
Detectar la modificación externa por fecha de modificación y advertir es el mínimo, y es CA-108.7.

## Criterios de aceptación

```gherkin
Escenario: CA-108.1 · Toda la configuración es alcanzable
  Dado el esquema de configuración con sus 39 campos en 10 secciones
  Cuando se recorre el panel
  Entonces cada campo del esquema tiene un control correspondiente

Escenario: CA-108.2 · Un campo nuevo sin control hace fallar la prueba
  Dado un campo añadido al modelo de configuración y no al panel
  Cuando se ejecuta la prueba de cobertura del esquema
  Entonces falla nombrando el campo que no tiene control

Escenario: CA-108.3 · Los errores se ven junto al campo
  Dado un valor de radio negativo introducido en el panel
  Cuando el usuario sale del campo
  Entonces el error se muestra junto a ese campo
  Y el botón de guardar queda inhabilitado

Escenario: CA-108.4 · Una regla entre campos también se valida
  Dado un umbral de severidad informativa mayor o igual que el de aviso
  Cuando el usuario intenta guardar
  Entonces la validación lo rechaza explicando la relación entre ambos campos

Escenario: CA-108.5 · Guardar preserva la documentación del archivo
  Dado un archivo de configuración con sus 46 líneas de comentarios
  Cuando se guarda un único campo desde el panel
  Entonces el archivo conserva todos sus comentarios y el orden de sus secciones
  Y el resto del contenido es idéntico salvo el campo modificado

Escenario: CA-108.6 · Una interrupción no deja el archivo a medias
  Dado un guardado interrumpido antes de completarse
  Cuando se inspecciona el sistema de archivos
  Entonces el archivo original está intacto
  Y no queda ningún archivo temporal huérfano

Escenario: CA-108.7 · Una edición externa no se pisa en silencio
  Dado que el archivo cambió en disco después de que el panel lo cargara
  Cuando el usuario intenta guardar
  Entonces el sistema advierte del conflicto antes de escribir
  Y no sobrescribe sin confirmación

Escenario: CA-108.8 · Nunca queda una configuración inválida en disco
  Dado un conjunto de valores que no valida contra el esquema
  Cuando se intenta guardar
  Entonces la escritura se rechaza por completo
  Y el archivo anterior se conserva sin cambios

Escenario: CA-108.9 · El usuario sabe que hace falta reiniciar
  Dado un guardado correcto
  Cuando termina la operación
  Entonces el panel indica que los cambios se aplican al reiniciar el agente

Escenario: CA-108.10 · El archivo sigue siendo accesible
  Cuando el usuario abre el menú de bandeja
  Entonces encuentra tanto la entrada que abre el panel como la que abre el archivo
```

## Definición de hecho

- [ ] Enmienda E-02 y ADR-019 escritos **antes** que el panel
- [ ] Panel con secciones plegables cubriendo los 39 campos, y prueba de cobertura del esquema
- [ ] Escritura con `tomlkit`, atómica, con respaldo y con detección de modificación externa
- [ ] El menú de bandeja ofrece las dos vías
- [ ] Restaurar valores por defecto por sección y para el archivo completo

## Fuera del corte de la v1.0

Especificados aquí para que quien retome el trabajo no los rediseñe, pero **no bloquean el
release**:

| Ítem | Capacidad | Requisito | Por qué se difiere |
|---|---|---|---|
| **B-37** | El mismo panel en el frontend de terminal | REQ-GUI-006 `[SHOULD]` | Paridad deseable; el modo headless ya tiene su panel de estado |
| **B-38** | Aplicar los cambios sin reiniciar | REQ-GUI-007 `[SHOULD]` | Es lo que permitiría retirar el aviso de CA-108.9. Toca el ciclo de vida de cinco componentes que hoy reciben su configuración al construirse |

## Trazabilidad

| Requisito | Criterios | Ítem |
|---|---|---|
| REQ-CFG-009 | CA-108.5 | B-35 |
| REQ-CFG-010 | CA-108.6 | B-35 |
| REQ-CFG-011 | CA-108.7 | B-35 |
| REQ-CFG-012 | CA-108.8 | B-35 |
| REQ-GUI-001 | CA-108.1, CA-108.2 | B-36 |
| REQ-GUI-002 | CA-108.3, CA-108.4 | B-36 |
| REQ-GUI-003 | *(definición de hecho)* | B-36 |
| REQ-GUI-004 | CA-108.9 | B-36 |
| REQ-GUI-005 | CA-108.10 | B-36 |
| REQ-GUI-006, 007 | — *(diferidos)* | B-37, B-38 |

**Por qué es P2 y no P1.** No cierra ningún hallazgo medido ni una promesa incumplida: la
configuración por archivo funciona. Es una mejora real de usabilidad para el destinatario del
producto, pero por el criterio del backlog va después de los P0 y de las capacidades que el proyecto
ya prometió por escrito. Si la prioridad de negocio es otra, es un cambio de una línea — **lo que no
cambia es que B-35 va antes**.
