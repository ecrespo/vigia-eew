# HU-109 · Un colaborador aporta el mismo día

> Épica **EP-9** · Prioridad **P1** · Esfuerzo M · Fase **F1**
> Ítem: B-34 · Requisitos: REQ-DEV-001..004

**Como** persona que quiere contribuir al proyecto,
**quiero** que preparar el entorno sea abrir el repositorio,
**para** dedicar mi primera tarde al código y no a averiguar por qué no tengo tkinter.

## Contexto

La decisión de abrir el proyecto a colaboradores **ya está tomada**, y con ella el bus factor 1 pasa
de riesgo aceptado a problema con solución en marcha. En la revisión anterior del backlog este ítem
era P3 con el disparador *"reevaluar si entra un segundo mantenedor"*; el disparador se cumplió.

El obstáculo concreto es específico de este proyecto y nada obvio: **necesita tkinter**, que no viene
en las imágenes base de Python. La CI ya lo resuelve usando el Python gestionado por `uv`
`[COMMITS: 0e707a1]`. Un colaborador chocaría con lo mismo sin ninguna pista de por dónde salir.

**Depende de la Fase 1**, no por burocracia: la imagen debe traer la versión de Python que el
proyecto exija. Construirla sobre 3.11 y rehacerla tras el cambio de runtime es trabajo duplicado.

**Lo que este ítem NO incluye:** la automatización de actualización de dependencias. Son dos cosas
que estaban juntas por accidente — un devcontainer sirve a quien contribuye; la automatización sirve
a quien mantiene, y su coste de triaje no cambia por tener colaboradores. Queda como B-39,
condicional.

## Criterios de aceptación

```gherkin
Escenario: CA-109.1 · El entorno se levanta sin pasos manuales
  Dado un contenedor de desarrollo recién creado a partir del repositorio
  Cuando se ejecuta "uv run vigia-eew --check-config"
  Entonces funciona sin instalar nada más

Escenario: CA-109.2 · Tkinter está disponible
  Dado el contenedor de desarrollo
  Cuando se importa el módulo de interfaz gráfica de la biblioteca estándar
  Entonces la importación tiene éxito

Escenario: CA-109.3 · El gate queda instalado solo
  Dado un contenedor de desarrollo recién creado
  Cuando se intenta confirmar un cambio que viola una regla del gate
  Entonces el commit se rechaza
  Y el colaborador no ha tenido que instalar los hooks manualmente

Escenario: CA-109.4 · Las pruebas de interfaz real se pueden ejecutar
  Dado el contenedor de desarrollo con display virtual
  Cuando se ejecuta la suite con las pruebas de interfaz gráfica habilitadas
  Entonces las 3 pruebas hoy excluidas por defecto se ejecutan y pasan

Escenario: CA-109.5 · La guía de contribución enlaza a los principios
  Cuando se consulta la guía de contribución
  Entonces documenta el gate de tres comandos y la convención de commits
  Y enlaza a la constitución del proyecto
```

## Definición de hecho

- [ ] Definición de contenedor con la versión de Python que exige el proyecto, gestor y bibliotecas de Tk
- [ ] Comando posterior a la creación que sincroniza dependencias e instala los hooks
- [ ] Display virtual configurado y las 3 pruebas de interfaz real pasando
- [ ] Guía de contribución escrita y enlazada desde el README

## Trazabilidad

| Requisito | Criterios | Ítem |
|---|---|---|
| REQ-DEV-001 | CA-109.1, CA-109.2 | B-34 |
| REQ-DEV-002 | CA-109.3 | B-34 |
| REQ-DEV-003 | CA-109.4 | B-34 |
| REQ-DEV-004 | CA-109.5 | B-34 |

**Permitido por la enmienda [E-03](../00-ENMIENDAS-CONSTITUCION.md).** Sin ella, un devcontainer
violaría la restricción de stack *"Contenedores: ninguno"*. La enmienda acota esa restricción al
producto, que es lo que siempre quiso decir.
