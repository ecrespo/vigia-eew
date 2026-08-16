# Configuration and startup

How the agent learns where the user is, what it should care about, and how it
comes back after a reboot. These decisions are mostly about *not* asking the
user for things, while keeping the network out of paths that must work offline.

## Config is a validated TOML file, read-only

Settings live in `config.toml`, parsed with stdlib `tomllib` and validated by
pydantic into [[src/vigia_eew/config.py#Settings]].

Severity thresholds and per-source blocks are nested structures, which `.env`
represents badly. Validation at load time means a typo surfaces at startup
(`--check-config`) rather than as a filter that silently accepts nothing.

`load_config` is deliberately **pure**: it reads and validates, and does no
networking and no state I/O. That boundary is what keeps the startup logic
below testable, and it is why `config.py` only reports *whether* a manual
`[reference]` was present rather than resolving one itself.

## The reference point is manual, with a one-time IP fallback

If the user defines `[reference]`, that is the location. If they do not,
[[src/vigia_eew/app.py#Application]] resolves one by IP exactly once before
starting the pipeline and caches it in the persisted state.

A user who configures nothing would otherwise get a radius filter centered on a
default city that is not theirs — silently wrong, and wrong in the direction of
missing real alerts. Detecting once and caching means the third-party lookup
happens on first run only; with a manual reference or a cached one, the API is
never called at all.

Failure does not cache: no network, a timeout, or an unexpected response falls
back to the built-in default and leaves the cache empty so the next startup can
retry. Detecting on *every* startup was rejected — a machine's location does not
change between boots, and it would make startup depend on the network forever.

OS-level geolocation (CoreLocation / Windows Location API / GeoClue) is more
accurate and was rejected: three native integrations and three permission
prompts, against a project premise of one portable Python core.

This is the project's one deliberate privacy exception: the IP lookup exposes
the source IP to a third party. It is triggered only by the *absence* of
configuration, never with user-supplied data, and setting `[reference]` disables
it entirely.

## Simulation never touches the network

`--simulate` injects a fixed event and must work with no connectivity at all,
so it never triggers the IP resolution above — regardless of whether a manual
reference exists.

The mode exists to let a user verify that the alert actually appears,
undismissable, on their machine. If it required a network round-trip it would
fail in exactly the situation where someone is most likely to be testing.

## Autostart is native per OS, generated as pure data

Autostart is installed through the OS's own mechanism — systemd `--user` on
Linux, LaunchAgent on macOS, a scheduled task on Windows — chosen by
[[src/vigia_eew/autostart/__init__.py#create_installer]] behind a common
interface.

A cross-platform supervisor bundled into the app would duplicate what all three
systems already do well, and would itself need something to start it. Each
installer separates **generating** its artifact (unit file, plist, `schtasks`
command line) from **executing** the system command, so the generated content
is unit-tested on any platform while only the execution needs the real OS.

## Subprocess environments are sanitized when frozen

System binaries launched as subprocesses get a cleaned environment from
[[src/vigia_eew/subprocess_env.py#system_env]].

A PyInstaller onefile bundle exports loader variables (`LD_LIBRARY_PATH`,
`DYLD_LIBRARY_PATH`) pointing into its own extracted bundle. Inheriting those
makes system binaries — the sound player, the config editor — load the bundle's
libraries instead of the platform's and fail in ways that look like the feature
is broken rather than the environment being wrong.
