# Configuration

`config.toml` is the source of truth, and for six versions it was read-only by decision. ADR-007
chose `tomllib` — the standard library's reader, which has no writer — and recorded the
consequence in one line: *"writing config isn't needed in v1"*.

v1.0 contradicts that, so amendment E-02 and ADR-019 were published **before** any code was
written. [[src/vigia_eew/config_writer.py#ConfigWriter]] is what they permit.

## The file is still the source of truth, and the panel is another way in

The tray keeps its "Edit configuration…" entry alongside the one that opens the panel.

That is not politeness towards old habits: the file is what lets somebody version it with Git, copy
it between machines, and edit it over SSH. Replacing it with a panel would take all three away to
gain nothing.

The reader does not change at all. `tomllib` still parses the file at startup, and
[[src/vigia_eew/config_writer.py#ConfigWriter]] is imported only when something writes — so the
agent's startup path is byte for byte the one that shipped in v0.6.0.

## Why `tomlkit` and not a serialiser

The shipped file carries 46 lines of comments, and they are the only in-line help the user has.
Serialising `Settings` back out would produce a valid file with none of them, and the loss would
be silent and total on the first save.

`tomlkit` parses into a document that remembers its own formatting, so setting one key changes one
line. `tomli-w` was rejected for exactly the property it lacks; a second file merged at read time
was rejected because it creates two sources of truth for the same setting.

## What the writer refuses to do

Three refusals, each protecting something a save could otherwise destroy:

- **It will not write over somebody else's edit.** The panel is the first component that writes a
  file the user also edits by hand. The fingerprint — modification time and size — is taken at
  load and compared before writing; a mismatch raises instead of saving, and the way out is to
  load again. Persisting that fingerprint was rejected: the case it protects lives entirely
  inside one panel session.
- **It will not leave an invalid file on disk.** Everything is applied to an in-memory copy and
  validated against the same `Settings` schema the agent starts with. An invalid `config.toml`
  leaves the agent unable to start, which is Art. 3 territory — so validation happens before the
  disk is touched, not after.
- **It will not write a key the schema does not know.** Pydantic ignores unknown keys, so a typo
  would land in the file, be dropped at load, and sit there looking like a setting that had been
  applied.

## Only what changed is written

The writer takes the fields to change, not a whole configuration.

That is what keeps `[reference]` commented out when the user never touched it — and `[reference]`
being absent is precisely what enables the IP-based location detection (RF-33). A panel that wrote
every field on every save would silently disable that on the first save anybody made.

See [[lat.md/state#Reference point resolution happens once, in the application layer]].

## The backup is written before the rename, not after

Temp file plus `os.replace`, the same rule that governs `state.json`
([[lat.md/state#Persisted state]]), plus a `.bak` copy of the previous version.

The order matters: the window worth protecting is between "the original is gone" and "the new file
is in place", so the copy has to exist before the rename, not after it. One backup and not a
history — the file is meant to be versioned with Git by anyone who cares, and duplicating that
inside the product would add retention management to solve a solved problem.

## The panel is generated, not transcribed

[[src/vigia_eew/notify/config_panel.py#describe]] walks the configuration models and the type of
each field chooses its control; the constraints already on the field do the validating.

Forty-odd controls written by hand is forty-odd chances for a field added to the model never to
reach the interface, and nobody finds out until a user cannot find the option. Generated, a new
field appears by itself — and one whose shape the generator does not understand raises by name
rather than disappearing from the panel. See ADR-020.

The cost is real and declared: a few fields have a closed domain the schema does not express —
language, log level, timezone — and they carry a control listed in `CHOICES`. The coverage test
accepts those because they are declared, not because they were forgotten.

### Deciding and displaying are separate on purpose

`PanelModel` holds no widgets. Which controls exist, what a value means, whether it validates and
what will be written are decided without a display, and therefore tested without one;
`ConfigPanel` is the widget tree and decides nothing.

Validation runs the section's own model over what the panel holds, so the rule lives in exactly
one place. A failure that names a field lands on that field. One that names none — the severity
thresholds, where neither value is wrong on its own — belongs to the section, which is why
CA-108.4 exists as a criterion separate from CA-108.3.
