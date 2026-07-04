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
- 🚨 **Non-dismissable alert**: a front-most window, with sound, that only closes on acknowledgment.
- 📍 **Configurable geographic filter**: reference point, radius in km, and minimum magnitude.
- 🟢 **Cross-platform**: Linux, Windows, and macOS, with autostart on login.
- 📦 **Full distribution**: PyPI, `.exe`, `.dmg`, AppImage, `.deb`, `.rpm`.
- 🧪 **`--simulate` mode** to test the alert without waiting for a real earthquake.

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
pytest            # test suite
ruff check .      # lint
mypy src          # type check
vigia-eew --help  # console entry point
```

---

<div align="center">
<sub>Built with Spec-Driven Development · Source and docs in Spanish</sub>
</div>