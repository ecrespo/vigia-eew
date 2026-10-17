# HU-102 · El gate mide las ocho dimensiones

> Épica **EP-2** · Prioridad **P1** · Esfuerzo ≈ 1 jornada · Fases **F0** y **F2**
> Ítems: B-09, B-10, B-11, B-12, B-25, B-26 · Requisitos: REQ-OBS-003, 004, 006, 007

**Como** persona que mantiene el proyecto,
**quiero** que el gate rechace lo que el Art. 8 dice que debe rechazar,
**para** que la calidad deje de depender de que alguien se acuerde de mirarla.

## Contexto

El Art. 8 de la constitución dice que nada entra sin gate verde y que el gate mide **ocho
dimensiones**. Mide cinco. **Cobertura, formato, duplicación y complejidad se pueden calcular, pero
no fallan nunca**, porque nadie las conectó al gate.

La diferencia entre medir y exigir es la que separa un informe de un control: hoy 19 archivos
divergen del formato sin consecuencia alguna, y dos funciones superan complejidad cognitiva 12 sin
que nada lo señale.

**Un detalle de ejecución que evita un PR ilegible:** el formateo inicial de los 19 archivos va en un
commit propio, separado del que activa la regla. Mezclarlos produce un diff donde el cambio real es
imposible de encontrar.

## Criterios de aceptación

```gherkin
Escenario: CA-102.1 · La cobertura se exige por criticidad
  Dado que un módulo del pipeline baja su cobertura por debajo del 85 por ciento
  Cuando se ejecuta el pipeline de integración
  Entonces falla nombrando el módulo y su umbral

Escenario: CA-102.2 · Los umbrales distinguen por criticidad
  Cuando se inspecciona la configuración de cobertura
  Entonces exige 85 por ciento en pipeline y estado, 70 en ingesta y 40 en adaptadores
  Y cubre líneas y ramas, no solo líneas

Escenario: CA-102.3 · Un archivo sin formatear no entra
  Dado un archivo que no cumple el formato
  Cuando se intenta confirmar el cambio
  Entonces el hook lo rechaza antes de crear el commit

Escenario: CA-102.4 · El formateo inicial no contamina la historia
  Cuando se revisa el historial tras activar la regla de formato
  Entonces el reformateo masivo está en un commit propio
  Y ningún commit mezcla reformateo con cambio de lógica

Escenario: CA-102.5 · El lote rápido se puede ejecutar por separado
  Dado que las pruebas de integración y de interfaz gráfica llevan marcador
  Cuando se ejecuta "pytest -m 'not integration and not gui'"
  Entonces solo se ejecutan las unitarias
  Y el lote termina en un tiempo apto para el gate de commit

Escenario: CA-102.6 · La duplicación nueva se rechaza
  Dado un bloque de código duplicado por encima del umbral declarado
  Cuando se ejecuta el gate
  Entonces falla señalando las dos ubicaciones

Escenario: CA-102.7 · Ninguna función supera el umbral de complejidad
  Cuando se mide la complejidad cognitiva del código fuente
  Entonces ninguna función supera el umbral declarado
  Y las dos que hoy lo superan han quedado por debajo
```

## Definición de hecho

- [ ] El CI falla ante cobertura por debajo del umbral de cada módulo
- [ ] `ruff format --check .` en el gate, y los 19 archivos formateados en commit aislado
- [ ] Marcadores `integration` y `gui` aplicados y documentados
- [ ] Detección de duplicación y medición de complejidad en el gate
- [ ] `_parse_row` extraída de la lectura de GEOFON; la ramificación de la CLI simplificada

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-OBS-003 | CA-102.1, CA-102.2 | B-09 | `code-audit/` P2-1 |
| REQ-OBS-004 | CA-102.5 | B-11 | `code-audit/` P2-3 |
| REQ-OBS-006 | CA-102.3, CA-102.4 | B-10 | `code-audit/` P2-2: 19 archivos |
| REQ-OBS-007 | CA-102.6, CA-102.7 | B-12, B-25, B-26 | `code-audit/` P2-4, P3-5 |

**Nota sobre B-25.** Agrupa nueve ítems P3 de calidad sin riesgo —duplicación entre los dos lectores
FDSN, el acceso al estado, un fixture repetido, una espera en un test, tres pruebas sin aserción y
un `assert` en el modelo—. Van en **un solo PR** porque revisarlos por separado cuesta más que el
cambio.
