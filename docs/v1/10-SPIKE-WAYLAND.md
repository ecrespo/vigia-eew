# Veredicto del spike — presentación garantizada bajo Wayland

> Artefacto 10 del kit v1.0 · Tarea **T-131** · 2026-09-19
> Prepara **REQ-ALE-004** · Insumo de la decisión **D-1**
> **Veredicto: viable con condiciones.** Las condiciones son la mitad del veredicto.

## 1. La pregunta

¿Es alcanzable, por el camino que diseñó [ADR-010](../TECHNICAL-DESIGN.md), la promesa central del
producto —una alerta por encima de todas las ventanas, que solo se cierra al acusarla— en una
sesión Wayland?

Un spike que solo puede concluir que sí no es un spike. Este tenía derecho a decir que no.

## 2. Entorno y método

Todo lo que sigue está **medido en esta máquina**, no inferido de documentación ajena.

| | |
|---|---|
| Sesión | `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-0`, XWayland en `DISPLAY=:0` |
| Compositor | **GNOME Shell 50.1** (Mutter) |
| Escritorio | `ubuntu:GNOME` |
| Contraste | El mismo código bajo un servidor X puro (Xvfb), misma máquina |

## 3. Evidencia

### E-1 · El camino actual falla, y falla en silencio

| Llamada | Wayland/GNOME | X11 puro |
|---|---|---|
| `wm_attributes("-topmost", True)` | **aceptada sin error** | aceptada sin error |
| Releer `-topmost` | **`0`** | **`1`** |
| `overrideredirect(True)` | aceptada | aceptada |
| `-fullscreen` | aceptada, **`1`** | aceptada, `1` |

**Lo grave no es que falle: es que no hay forma de saberlo en el punto de llamada.** Tk devuelve
éxito y el compositor descarta el atributo. Ningún `try/except` lo detecta. Por eso T-130 razona
sobre la sesión en vez de confiar en el valor de retorno.

### E-2 · Ninguna vía de cliente existe en GNOME

Globales anunciados por el compositor, enumerados vía `wl_registry`:

| Protocolo | ¿Presente? | Para qué serviría |
|---|---|---|
| `zwlr_layer_shell_v1` | **ABSENTE** | Colocar una superficie en la capa *overlay*, por encima de todo |
| `zwp_input_inhibit_manager_v1` | **ABSENTE** | Impedir que la alerta se descarte |
| `zwlr_foreign_toplevel_manager_v1` | ABSENTE | Conocer/alterar otras ventanas |
| `xdg_wm_dialog_v1` | presente | Diálogo *modal respecto a su propia ventana padre*, no al sistema |

**Esto cierra la discusión sobre el lado cliente.** No es que Tkinter sea la herramienta
equivocada: **no existe protocolo Wayland alguno que un cliente pueda usar en GNOME** para
ponerse por encima de todo. Cambiar a GTK4, Qt o un cliente Wayland nativo no mueve esta fila.

### E-3 · No se puede inyectar código en el Shell en marcha

`org.gnome.Shell.Eval` devuelve `(false, "")` — deshabilitado, que es el estado endurecido normal
desde GNOME 41. La única vía dentro del compositor es una extensión instalada.

### E-4 · Instalar la extensión exige cerrar la sesión

Instalada en `~/.local/share/gnome-shell/extensions/`, con `metadata.json` declarando
`shell-version: ["48","49","50"]`:

| Comprobación | Resultado |
|---|---|
| `gnome-extensions list` | no aparece |
| `org.gnome.Shell.Extensions.ListExtensions` | no aparece |
| `EnableExtension` | **`false`** |
| `ReloadExtension` | **`"ReloadExtension is deprecated and does not work"`** |

Y en Wayland **no se puede reiniciar GNOME Shell** (no hay Alt+F2 `r`). La extensión no existe
para el Shell hasta el siguiente inicio de sesión. *(La extensión de prueba se retiró; no queda
nada instalado ni en dconf.)*

### E-5 · Pantalla completa sí se respeta

`-fullscreen` se aplica de verdad bajo Wayland: reportado `1` y geometría `3072x1920`, la pantalla
entera. Mutter coloca las ventanas a pantalla completa por encima de las normales.

## 4. Lo medido y lo razonado

Conviene separarlo, porque no todo tiene el mismo peso.

| Afirmación | Base |
|---|---|
| El camino actual no cumple la garantía en Wayland | **Medido** (E-1) |
| Ningún cliente puede cumplirla en GNOME | **Medido** (E-2) |
| La instalación de la extensión exige cerrar sesión | **Medido** (E-4) |
| Pantalla completa se respeta | **Medido** (E-5) |
| Una extensión *puede* dibujar por encima de todo | **Razonado, no medido** |

La última fila es honesta: no pude cargar la extensión sin cerrar tu sesión. El razonamiento es
sólido —`Main.layoutManager.addChrome()` añade el actor a `uiGroup`, que por construcción del
grafo de escena está por encima de `global.window_group`, y las extensiones de bloqueo de pantalla
que esta misma máquina ya ejecuta hacen algo equivalente— pero es razonamiento.

## 5. Las condiciones

Que sea alcanzable no es lo mismo que que salga a cuenta. Lo que E-2 y E-4 implican:

| Condición | Consecuencia |
|---|---|
| **Es específica de GNOME** | `zwlr_layer_shell_v1` cubriría sway y Hyprland, pero GNOME no lo implementa. **No hay una implementación de Wayland: hay una por escritorio.** KDE Plasma necesitaría la suya |
| **La instalación no basta** | El usuario instala el agente, la extensión queda escrita, y **la promesa no se cumple hasta que cierre y reabra sesión**. Para un producto cuyo valor es avisarte, un camino de instalación que silenciosamente no funciona hasta el siguiente arranque es peligroso, no incómodo |
| **La API de extensiones rompe cada 6 meses** | `metadata.json` declara versiones de Shell. Hoy es la 50. La cadencia de release del agente quedaría acoplada a la de GNOME |
| **Hay que empaquetar JavaScript** | El binario de PyInstaller y el wheel tendrían que instalar una extensión JS en el directorio del usuario |

**Reevaluación del coste.** El plan estima T-132 en 16–60 h. Esa cifra cubre *una* implementación.
Con E-2 sobre la mesa, cubrir Wayland significa una implementación por escritorio, más el
empaquetado de la extensión, más el mecanismo de aviso de "reinicia la sesión", más el
mantenimiento por cada versión de GNOME. **La estimación se queda corta**, y el spike existe
precisamente para decirlo antes y no después.

## 6. Lo que se puede hacer hoy, sin nada de lo anterior

**Pantalla completa (E-5).** `[notification] fullscreen` ya existe en la configuración y **se
respeta bajo Wayland**. Una alerta a pantalla completa cubre lo que el usuario está mirando aunque
no pueda declararse *always-on-top*. No es la garantía —otra ventana a pantalla completa, un juego
o un vídeo, sigue pudiendo quedar por encima, y no medí ese caso— pero es la mitigación que está
disponible ahora mismo y a coste cero.

## 7. Veredicto

**Viable con condiciones.**

- Alcanzable en **GNOME**, por la vía de ADR-010, con el coste que describe §5.
- **No alcanzable por ningún otro medio**: E-2 cierra el lado cliente de forma definitiva.
- **No hay una solución "para Wayland"**, solo una por escritorio.
- El coste real está por encima de lo estimado, y la fricción de instalación es un riesgo de
  producto, no solo de ingeniería.

## 8. Qué significa para D-1

D-1 pregunta si la alerta bajo Wayland bloquea el release de la v1.0.0. Con esta evidencia:

- **Si `[MUST]`**: la v1.0.0 se ata a GNOME, a una extensión JS empaquetada, a un requisito de
  reinicio de sesión y a la cadencia de GNOME. Y aun así, un usuario de KDE/Wayland seguiría sin
  la garantía, así que la promesa tampoco quedaría cumplida "en Wayland".
- **Si `[SHOULD]`**: la v1.0.0 sale con la garantía en Windows, macOS y Linux/X11 —declarado y
  visible, que es lo que hizo T-130—, con pantalla completa como mitigación en Wayland, y la
  extensión de GNOME pasa a ser una mejora posterior sin atar el corte.

**Recomendación del spike:** `[SHOULD]`. La razón no es que sea difícil, sino que **E-2 impide que
cumplirlo signifique lo que la promesa dice**. "La alerta funciona en Wayland" seguiría siendo
falso para todo escritorio que no sea GNOME, y una v1.0.0 que promete eso vuelve al problema que
T-130 acaba de arreglar: prometer de más.

La decisión sigue siendo del mantenedor.
