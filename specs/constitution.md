# Constitución — Vigía-eew

> Versión 1.0 · Ratificada: 2026-08-16 · Última enmienda: —
> Ámbito: `ecrespo/vigia-eew` (agente, empaquetado, documentación y specs)

Estos son los principios **no negociables** del proyecto. Se escriben una vez y se
revisan rara vez, con enmienda registrada. Todo artefacto posterior —PRD, delta spec,
ADR, PR— se valida contra ellos.

Hasta ahora estos principios existían, pero **dispersos**: repartidos entre 18 ADRs,
`lat.md/` y la costumbre del autor. Este documento los reúne para que un contribuidor
—humano o agente— los herede sin tener que reconstruirlos leyendo el historial.

## Artículos

### Art. 1 — La alerta es imposible de descartar por accidente
EL SISTEMA DEBERÁ presentar toda alerta relevante en una ventana sin decoración, siempre
encima, que recupera el foco al perderlo, y que **solo** se cierra mediante un
reconocimiento explícito del usuario. Ningún frontend —actual o futuro— podrá relajar
este contrato: si un toolkit no puede cumplirlo, se cambia el toolkit, no el contrato.

*Racional: es la razón de existir del producto. Escape, la X y el clic-fuera son formas
de que una advertencia se cancele por reflejo antes de leerse.*

### Art. 2 — Ante la duda, no se suprime
EL SISTEMA DEBERÁ dejar pasar el evento cuando un filtro no pueda evaluarse (zona horaria
inválida, país indeterminado, ubicación desconocida). Todo filtro nuevo DEBERÁ fallar en
esa misma dirección y DEBERÁ registrar por qué quedó inerte.

*Racional: una alerta perdida es un fallo de seguridad; una alerta de más, una molestia.
La asimetría es deliberada y no se negocia por elegancia.*

### Art. 3 — Ningún fallo parcial tumba el proceso
EL SISTEMA DEBERÁ supervisar cada tarea de larga vida y reiniciarla con backoff
exponencial con jitter, sin terminar el proceso. Todo efecto dependiente del entorno
—sonido, bandeja, toast, geolocalización— DEBERÁ capturar su propia excepción, registrar
una advertencia y permitir que la ingesta continúe.

*Racional: un agente de seguridad que muere en silencio es peor que no tener agente,
porque el usuario cree estar cubierto.*

### Art. 4 — Todo instante es UTC tz-aware; la hora local solo existe al presentar
EL SISTEMA DEBERÁ rechazar todo `datetime` *naive* en el modelo de datos y normalizar a
UTC en el borde de entrada. La conversión a hora local DEBERÁ ocurrir únicamente en la
capa de presentación, salvo la regla de día calendario local, que es un concepto humano y
DEBERÁ usar la zona configurada.

*Racional: mezclar naive y aware en la aritmética de ventanas de dedup produce respuestas
incorrectas en silencio, no excepciones.*

### Art. 5 — Las dependencias fluyen hacia el núcleo, y una regla lo verifica
EL SISTEMA DEBERÁ mantener el dominio (`pipeline/`, núcleo compartido) libre de
importaciones de infraestructura: `httpx`, `websockets`, `tkinter`, `pystray`, `textual`
y `subprocess` no pueden aparecer ahí. EL EQUIPO DEBERÁ hacer cumplir esta frontera con
una regla ejecutable en el gate, no con revisión manual.

*Racional: es la propiedad de la que depende el 89 % de cobertura. Una regresión aquí
pasaría los 345 tests sin levantar una alarma.*

### Art. 6 — Los efectos se inyectan
EL SISTEMA DEBERÁ recibir por constructor todo efecto externo —reloj, `sleep`, cliente
HTTP, conexión WebSocket, fábrica de ventana, ejecutor de subprocesos— en vez de
instanciarlo internamente.

*Racional: es lo que permite testear reconexión, backoff y "hoy" sin red ni reloj real, y
lo que hizo posible que Tkinter y Textual compartan controlador sin duplicarlo.*

### Art. 7 — Sin credenciales, sin telemetría, y una sola excepción de privacidad
EL SISTEMA DEBERÁ operar sin API keys ni credenciales, consumir las fuentes en modo solo
lectura y no enviar datos del usuario a terceros. La única excepción admitida es la
geolocalización por IP, que DEBERÁ dispararse solo ante la **ausencia** de configuración
manual, ejecutarse una vez, cachearse, y poder desactivarse por completo definiendo
`[reference]`. Cualquier excepción futura DEBERÁ documentarse en un ADR antes de
implementarse.

*Racional: es software que vigila a su usuario para protegerlo; la confianza es parte del
producto.*

### Art. 8 — La spec y la intención se actualizan como parte del trabajo, no después
EL EQUIPO DEBERÁ registrar toda decisión de diseño no obvia en un ADR de la serie de
`docs/TECHNICAL-DESIGN.md`, con al menos una alternativa rechazada y su porqué; DEBERÁ
anclar el código gobernado por esa decisión con un comentario `# @lat:`; y DEBERÁ dejar
`lat check` en verde antes de cerrar la tarea. Todo cambio a comportamiento ya
especificado DEBERÁ entrar como Delta Spec en `changes/`.

*Racional: el valor diferencial de este repo es que el *porqué* está escrito. Ese activo
se mantiene con disciplina en cada tarea o se pierde en tres meses.*

## Restricciones del stack

Decidido; no se rediscute por feature.

| Área | Decisión | Referencia |
|---|---|---|
| Lenguaje | Python ≥3.11 (piso fijado por `tomllib` en stdlib) | ADR-007 |
| Estilo arquitectónico | Monolito modular + Pipes & Filters + Ports & Adapters + Supervisor | ADR-022 |
| Despliegue | Un agente por máquina; **sin relay central** | ADR-008 |
| Red | `websockets` (push) + `httpx` (REST). Sin Tornado, sin aiohttp | ADR-009 |
| Validación | pydantic v2 en todo borde externo | ADR-007 |
| Persistencia | JSON atómico local vía `platformdirs`. Sin base de datos | ADR-018 |
| UI por defecto | Tkinter (stdlib). TUI con Textual para headless | ADR-003, ADR-013 |
| Dependencias extra | Solo para frontends opcionales, y cada una documentada como excepción | RNF-06 |
| Tooling | uv + hatchling; ruff (line-length 100), mypy `strict`, pytest | ADR-007 |
| Gate | pre-commit en dos etapas con paridad frente a CI | `.pre-commit-config.yaml` |

## Enmiendas

| Fecha | Artículo | Cambio | Razón | Aprobado por |
|---|---|---|---|---|
| — | — | Ratificación inicial | Consolidar principios dispersos en 18 ADRs y `lat.md/` | pendiente |

## Constitution check

Usar en cada PRD, delta spec y ADR. Un artefacto que no pueda responder estas preguntas
no está listo para implementarse:

- [ ] ¿Preserva Art. 1? Si toca la presentación de alertas, ¿sigue siendo imposible
      descartarla por accidente?
- [ ] ¿Preserva Art. 2? Si añade un filtro o una condición de supresión, ¿falla dejando
      pasar?
- [ ] ¿Preserva Art. 3? Si añade un efecto de entorno, ¿está aislado del pipeline?
- [ ] ¿Preserva Art. 4? ¿Los instantes nuevos son UTC tz-aware?
- [ ] ¿Preserva Art. 5? ¿Introduce alguna importación de infraestructura en el dominio?
- [ ] ¿Preserva Art. 6? ¿Los efectos nuevos se inyectan?
- [ ] ¿Preserva Art. 7? ¿Añade alguna llamada a terceros o algún dato saliente?
- [ ] ¿Preserva Art. 8? ¿Tiene ADR, backlinks `# @lat:` y `lat check` en verde?
