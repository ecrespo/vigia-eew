# HU-104 · Añadir una fuente cuesta tres puntos

> Épica **EP-4** · Prioridad **P1** · Esfuerzo ≈ 1 jornada · Fase **F3**
> Ítems: B-18, B-21 · Requisito: REQ-ING-009

**Como** persona que quiere añadir una red sísmica nueva,
**quiero** que hacerlo consista en registrar su especificación y escribir su ingestor,
**para** no tener que encontrar y modificar cinco archivos que nadie me señala.

## Contexto

Hoy añadir una quinta fuente toca **cinco archivos o más**:

| Punto | Qué hay que tocar |
|---|---|
| Normalización | Una escalera `if/elif` por fuente `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]` |
| Composición | Una fábrica por fuente en `Application` |
| Supervisión | El cableado de la tarea nueva |
| Configuración | Una sección y su modelo |
| Pruebas | Las de la fuente |

Los tres primeros son **accidentales**: existen porque el conocimiento de "qué fuentes hay" está
repartido en vez de declarado. Un registro `dict[Source, SourceSpec]` los colapsa en uno.

`wiring.py` va con esto y no aparte: `Application` tiene hoy **fan-out 25 sobre 40 módulos** —el
hallazgo P1-1 de la evaluación de arquitectura— precisamente porque compone además de orquestar.
Separar la composición es lo que deja sitio al registro.

**Dos cosas que este cambio NO hace**, para que no crezca: no unifica los dos lectores FDSN (eso es
condicional, y su ADR lo difirió hasta que exista una quinta fuente FDSN), y no introduce un
contenedor de inyección de dependencias — indirección sobre un grafo de 40 módulos que cabe en la
cabeza.

## Criterios de aceptación

```gherkin
Escenario: CA-104.1 · Una fuente nueva se añade en tres puntos
  Dado el registro declarativo de fuentes
  Cuando se añade una fuente de prueba con su ingestor y su especificación
  Entonces solo se modifican tres archivos: el registro, el ingestor y su prueba

Escenario: CA-104.2 · La normalización deja de ramificar por tipo de fuente
  Cuando se inspecciona el normalizador
  Entonces no contiene ninguna escalera condicional por fuente
  Y cada fuente aporta su propia función de conversión desde el registro

Escenario: CA-104.3 · Una fuente desconocida no rompe el arranque
  Dado un identificador de fuente que no está en el registro
  Cuando el sistema intenta componer la ingesta
  Entonces falla al arrancar con un mensaje que nombra la fuente
  Y no se queda ejecutando con esa fuente silenciosamente ausente

Escenario: CA-104.4 · La composición está separada de la orquestación
  Cuando se mide el acoplamiento saliente del módulo de aplicación
  Entonces es menor o igual que 8
  Y la construcción de dependencias vive en un módulo de cableado propio

Escenario: CA-104.5 · El comportamiento de las cuatro fuentes actuales no cambia
  Dado el registro con las cuatro fuentes existentes
  Cuando se ejecuta la suite completa
  Entonces todas las pruebas de ingesta pasan sin modificarse

Escenario: CA-104.6 · Deshabilitar una fuente sigue siendo una línea de configuración
  Dado el registro declarativo
  Cuando una fuente se marca como deshabilitada en la configuración
  Entonces su tarea no se crea
  Y las demás fuentes siguen funcionando con independencia
```

## Definición de hecho

- [ ] `SourceSpec` definido y las cuatro fuentes registradas
- [ ] Sin escaleras por tipo de fuente en el pipeline
- [ ] `wiring.py` separado; fan-out de `app` ≤ 8 y su tamaño por debajo de 300 líneas
- [ ] La suite de ingesta pasa sin cambios

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-ING-009 | CA-104.1, 104.2, 104.3, 104.5, 104.6 | B-18 | `arch-eval/` P2-4 · ADR-001 |
| REQ-ING-009 | CA-104.4 | B-21 | `arch-eval/` **P1-1**: fan-out 25/40 |
