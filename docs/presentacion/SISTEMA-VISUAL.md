# Sistema visual del deck — Vigía-eew

> Definido el 2026-09-06 para `vigia-eew-evaluacion.pptx`.
> **Cualquier actualización posterior de este deck debe respetarlo.** La fuente canónica es
> [`generador/design.js`](generador/design.js): cambiar un color ahí lo cambia en las 17 slides.

## Paleta

| Rol | Color | Peso visual | Uso |
|---|---|---|---|
| **Dominante** | `1B2028` slate casi negro | ~65 % | Fondo de portada, secciones de énfasis y cierre |
| Soporte oscuro | `2E3744` | — | Tarjetas sobre fondo oscuro |
| Soporte claro | `EEF1F5` | — | Fondo de slides de contenido |
| Tarjeta | `FFFFFF` | — | Bloques sobre fondo claro |
| **Acento** | `00B4A6` turquesa | ~10 % | Navegación, énfasis, el motivo. **Nunca indica severidad** |

### Semánticos de severidad — uso exclusivo

Estos cuatro colores **solo** aparecen para indicar severidad. Si un elemento no comunica
severidad, no puede usarlos.

| Nivel | Color | Significado |
|---|---|---|
| P1 | `C0392B` | Crítico: explotable o pérdida de datos |
| P2 | `E8A33D` | Debilita defensas |
| OK / P3 | `27AE60` | Sano, o calidad sin riesgo |
| No evaluado | `8892A6` | Falta la herramienta, no falta el hallazgo |

La slide 2 del deck publica esta leyenda, para que quien lo lea sepa la regla antes del primer
dato.

## Motivo visual

**Anillos concéntricos** en la esquina inferior derecha, en el color de acento, con transparencia
creciente hacia fuera. Se repite en **las 17 slides** sin excepción.

No es decoración arbitraria: es el ícono de bandeja del propio producto —un círculo con ondas
concéntricas— y por eso el deck se ve diseñado para *este* proyecto y no para cualquier otro.

Implementado en `design.js::motif()`. Tres elipses sin relleno sólido, ancladas fuera del borde
para que solo entren los arcos.

## Tipografía

Ambas de la lista segura: se renderizan con anchos fieles en el QA visual **y** vienen con Office,
así que la comprobación de desbordes es de fiar.

| Elemento | Fuente | Tamaño |
|---|---|---|
| Título de slide | Cambria (serif) | 32 pt bold |
| Título de portada | Cambria | 44 pt bold |
| Antetítulo (kicker) | Calibri | 11 pt bold, versalitas, `charSpacing: 2` |
| Encabezado de sección | Cambria | 15-17 pt bold |
| Cuerpo | Calibri | 12-13,5 pt |
| Cifras grandes | Cambria | 36-60 pt bold |
| Pie / fuente | Calibri | 11 pt cursiva |

## Reglas de composición

- Márgenes mínimos de 0,5"; el contenido empieza en `x = 0.7`.
- Separación entre bloques: 0,3" o más. Nunca menos.
- Texto de párrafo alineado a la izquierda; solo se centran títulos y etiquetas dentro de círculos.
- `valign: "top"` en todo cuadro de texto multilínea — sin él, pptxgenjs centra verticalmente y
  abre huecos entre un encabezado y su cuerpo.
- `margin: 0` en todo cuadro de texto que deba alinearse con una forma.
- Las notas del orador llevan la trazabilidad al documento de origen.

### Lo que este sistema NO usa

- **Sin barras ni franjas de acento**: ni cabeceras de ancho completo, ni bandas laterales, ni
  filos de color en las tarjetas. Se distinguen los bloques con fondo, sombra suave e íconos.
- **Sin líneas bajo los títulos.**
- Sin fondos crema o beige.
- Sin slides de solo texto: cada una lleva tarjetas, cifras, un gráfico o el motivo como elemento.

## Cómo actualizar el deck sin romper el sistema

```bash
cd docs/presentacion/generador
npm install pptxgenjs        # solo si el require falla
node build.js                # escribe el .pptx
```

Después, **el QA de tres partes es obligatorio**, igual que en la creación:

```bash
# 1 · contenido
markitdown vigia-eew-evaluacion.pptx | grep -inE "\bx{3,}\b|lorem|ipsum|\[insert|undefined|NaN"
# 2 · archivo
python <skill-pptx>/scripts/office/validate.py vigia-eew-evaluacion.pptx
# 3 · visual — render e inspección slide por slide
python <skill-pptx>/scripts/office/soffice.py --headless --convert-to pdf vigia-eew-evaluacion.pptx
rm -f slide-*.jpg && pdftoppm -jpeg -r 110 vigia-eew-evaluacion.pdf slide
```

> El grep de placeholders de la plantilla marca `\bTODO` sin distinguir mayúsculas, y eso captura
> **"Todos"** y **"Todo"**, palabras normales en español. Al revisar los resultados hay que
> descartarlas: son falsos positivos del patrón, no contenido sin terminar.

## Resultado del QA de la versión actual

| Parte | Resultado |
|---|---|
| Contenido | 17 slides, orden correcto, sin placeholders reales |
| Archivo | `validate.py` → **All validations PASSED** |
| Visual | 17 slides renderizadas e inspeccionadas una por una; **5 defectos encontrados y corregidos** |

Los cinco defectos, para que no se repitan: sentencia partida por centrado vertical (slides 2 y 9),
columnas desalineadas entre sí (slide 4), eje de valores con mínimos negativos en el gráfico
(slide 8), y separación menor de 0,3" entre la rejilla de atributos y la tarjeta contigua
(slide 12). Los cuatro primeros tenían la misma causa raíz: **pptxgenjs centra verticalmente el
texto por defecto**.
