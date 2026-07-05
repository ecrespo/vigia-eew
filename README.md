# 🌐 Vigía-eew

### Real-time earthquake alerts for your desktop. Impossible to ignore.


## What is it?

**Vigía** (`vigia-eew`) is a cross-platform desktop agent that monitors earthquakes in **real time** and fires an alert that **can't be ignored or dismissed by accident**.

It connects over **WebSocket** to the **EMSC** real-time feed (push — no constant polling) and uses the **USGS FDSN** service as a reconciliation fallback so no event is missed. When an earthquake occurs within your configured radius, Vigía instantly displays its **magnitude, location, distance from your reference point, and depth** — and stays on screen until you explicitly acknowledge it.

It runs on **Linux, Windows, and macOS**, with no API keys, no paid services, and no dependency on any phone.

## Why?

A regular desktop notification gets silenced by Do Not Disturb, dismissed with a stray click, or buried behind other windows. In a seismic emergency, that's exactly what must not happen. Vigía forces an alert window to the front, with sound scaled to severity, that only disappears once you confirm you've seen it.

It was born in the aftermath of the June 2026 Venezuela earthquake, with a clear goal: a **self-hosted, free, and robust** tool that each machine can run on its own, with no single point of failure. Depending on your distance from the epicenter, the notification may reach you **before the most destructive seismic waves**; and even when it doesn't, it guarantees the alert isn't missed and is logged.

## Key features

- 🛰️ **Real WebSocket push (EMSC)** as the primary channel — no constant polling.
- 🔁 **REST fallback (USGS FDSN)** that reconciles and recovers anything the WebSocket may drop.
- 🇻🇪 **FUNVISIS local coverage (Venezuela only)**: polls the Venezuelan national network so the small local quakes (M2–3) that EMSC/USGS don't catalog still trigger alerts. Polling (no push); enabled by default, harmless elsewhere (its events fall outside your radius).
- 🚨 **Non-dismissable alert**: a front-most window, with sound, that only closes on acknowledgment.
- 📍 **Configurable geographic filter**: reference point, radius in km, and minimum magnitude — auto-detected by IP geolocation if you don't set one manually.
- 🌎 **Optional country filter**: only notify earthquakes in your own country (offshore/coastal quakes kept), determined offline — opt-in, off by default.
- 🟢 **Cross-platform**: Linux, Windows, and macOS, with autostart on login.
- 📦 **Full distribution**: PyPI, `.exe`, `.dmg`, AppImage, `.deb`, `.rpm`.
- 🧪 **`--simulate` mode** to test the alert without waiting for a real earthquake.
- 🖥️ **System tray icon**: connection status, last alert, pause/resume notifications, edit config, quit — best-effort, never blocks startup if unavailable on your desktop.
- ⌨️ **Headless TUI dashboard (`--tui`)**: run the agent on a server over SSH with no display — a terminal dashboard with live status, an alerts log, and a non-dismissable modal alert (ENTER acknowledges). Combine with `--simulate` to test it.

## Installation

There are two ways to install Vigía: a **prebuilt package** (recommended for everyday
desktop use) or **from source** (for development or unsupported platforms).

### Option A — Prebuilt package (recommended)

Download the artifact for your OS from the
[**latest GitHub Release**](https://github.com/ecrespo/vigia-eew/releases/latest). No Python
installation is required — the binary is self-contained.

| OS | Artifact | Install |
|---|---|---|
| **Linux** | `vigia-eew-*-x86_64.AppImage` | `chmod +x vigia-eew-*.AppImage && ./vigia-eew-*.AppImage` |
| **Linux (Debian/Ubuntu)** | `vigia-eew_*_amd64.deb` | `sudo apt install ./vigia-eew_*_amd64.deb` |
| **Linux (Fedora/RHEL)** | `vigia-eew-*.x86_64.rpm` | `sudo dnf install ./vigia-eew-*.x86_64.rpm` |
| **Windows** | `vigia-eew.exe` | Double-click, or run it from a terminal. |
| **macOS** | `vigia-eew-*.dmg` | Open the `.dmg` and drag the app to *Applications*. |

The `.deb`/`.rpm` packages install a `vigia-eew` command on your `PATH`; the AppImage, `.exe`,
and `.app` are run directly.

### Option B — From source (Python 3.11+)

Requires **Python 3.11 or newer**. With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/ecrespo/vigia-eew.git
cd vigia-eew
uv venv && uv pip install -e .        # add ".[dev]" for the test/lint tooling
uv run vigia-eew --help
```

Or with plain `pip`:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
vigia-eew --help
```

> If your release also publishes to PyPI, `pipx install vigia-eew` (or `pip install
> vigia-eew`) works too — PyPI upload is optional in CI, so check the release notes.

## Configuration

Vigía runs with **sensible defaults centered on Caracas** and needs **no configuration to
start**. To customize it, create a `config.toml`. On first run Vigía **auto-creates** one
from the bundled template at the path below; you can also copy
[`config.toml.example`](./src/vigia_eew/config.toml.example) there by hand and edit it.

**Where the file lives** (the default location Vigía reads on startup):

| OS | Path |
|---|---|
| **Linux** | `~/.config/vigia-eew/config.toml` |
| **macOS** | `~/Library/Application Support/vigia-eew/config.toml` |
| **Windows** | `%LOCALAPPDATA%\vigia-eew\config.toml` |

You can also point at any file explicitly with `--config <path>`. From the desktop tray icon,
**"Edit configuration…"** opens the file currently in use (creating it from the template if
needed).

**Most useful settings** (see `config.toml.example` for the full schema):

```toml
[reference]                 # your location; delete this whole section to auto-detect by IP
name = "Caracas"
lat = 10.4806
lon = -66.9036

[filter]
radius_km = 300.0           # only alert on earthquakes within this radius
min_magnitude = 2.5         # raise to ignore smaller quakes (e.g. 3.0)
country_filter = false      # true = don't notify quakes in *other* countries (offshore kept)
country = "auto"            # "auto" derives it from the reference point, or set "VE", "CO", ...

[notification]
fullscreen = false          # make the alert take the whole screen
sound = true                # play a severity-scaled sound
tray_icon = true            # show the system tray icon (best-effort)
language = "auto"           # "auto" = detect from OS locale; or "en" / "es"
```

- **Location** — set `[reference]` manually, **or delete/comment the whole section** to have
  Vigía detect your location by IP on first startup (cached afterwards).
- **What triggers an alert** — `radius_km` and `min_magnitude` in `[filter]`.
- **Only my country** — set `[filter] country_filter = true` to suppress earthquakes in
  other countries (offshore/coastal quakes are kept). Off by default.
- **Language** — `[notification] language` (`"auto"`, `"en"`, or `"es"`).
- **FUNVISIS (Venezuela)** — `[sources.funvisis]` polls the Venezuelan network for local
  quakes EMSC/USGS miss. Enabled by default; it only reports Venezuelan events (harmless
  elsewhere — they fall outside your radius) and it's polled over plain HTTP (FUNVISIS has
  no HTTPS). Set `enabled = false` to turn it off.

Validate a config without starting the agent:

```bash
vigia-eew --check-config              # uses the default path
vigia-eew --config ./my.toml --check-config
```

## Usage

### On the desktop (default)

Just run it — from the launcher (packaged app) or the console:

```bash
vigia-eew
```

Vigía starts in the background and connects to the feeds. From then on:

- When a qualifying earthquake occurs, a **front-most, non-dismissable alert window** appears
  with sound, showing magnitude, place, distance, and depth. It **stays until you click
  ACKNOWLEDGED** — a stray click, `Esc`, or the window's X won't close it.
- A **system tray icon** shows connection status and the last alert, and lets you
  **pause/resume** notifications, **edit the configuration**, or **quit** (best-effort; if your
  desktop can't show a tray icon, the agent still runs).

**Start automatically on login** (installs a systemd user service / LaunchAgent / scheduled
task, depending on the OS):

```bash
vigia-eew --install-autostart
vigia-eew --uninstall-autostart   # to remove it
```

**Test the alert** without waiting for a real earthquake (injects a simulated M6.1 near La
Guaira):

```bash
vigia-eew --simulate
```

### From the console (CLI)

Run `vigia-eew --help` to see every flag:

| Flag | What it does |
|---|---|
| *(none)* | Start the full agent with the desktop GUI + tray icon. |
| `--tui` | Run the **headless terminal dashboard** instead of the desktop GUI (for servers over SSH with no display). |
| `--simulate` | Inject a simulated earthquake to test the alert. Combine with `--tui`. |
| `--config <path>` | Use a specific `config.toml`. |
| `--check-config` | Validate the configuration and print the reference point, then exit. |
| `--install-autostart` / `--uninstall-autostart` | Install/remove autostart on login. |
| `--version` | Print the version and exit. |

**Headless / over SSH — the TUI dashboard:**

```bash
vigia-eew --tui                # live status bar + alerts log in the terminal
vigia-eew --tui --simulate     # same, with a test alert to see the modal
```

The TUI shows the WebSocket connection status and a log of recent alerts. Each qualifying event
opens a **non-dismissable modal** inside the terminal that only **ENTER** acknowledges (`Esc` is
disabled — same "impossible to ignore" contract as the desktop window). Keys: **`p`**
pause/resume notifications, **`q`** quit. There is no tray icon or toast in this mode.

## Development

The project uses a `src/` layout, so it must be installed in **editable mode** before
running the tests or the CLI from a checkout (otherwise `import vigia_eew` fails).

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv venv
uv pip install -e ".[dev]"      # runtime + dev deps (pytest, ruff, mypy)
```

Or with plain `pip`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Then run the checks:

```bash
uv run pytest      # test suite
uv run ruff check .   # lint
uv run mypy src    # type check
uv run vigia-eew --help  # console entry point
```

---

<div align="center">
<sub>Built with Spec-Driven Development · Source and docs in Spanish</sub>
</div>