"""Tests for packaging asset validation (REQ-OPS-007, HU-107).

Two consecutive releases shipped broken because of a packaging resource:
`7b1c71c` (an invalid placeholder icon) and `c38d9f6` (a valid PNG whose
resolution linuxdeploy rejects). Both were found by the packager, which
means both were found after the build had already started -- and the second
proves that "is it a PNG" is not the question. The question is whether it is
a PNG the packager will accept.

Validation is stdlib-only on purpose: it has to be able to run before
anything is installed, and the generated AppImage icon is built the same way
in `packaging/build_linux.sh` for the same reason.
"""

from __future__ import annotations

import importlib.util
import re
import struct
import sys
import wave
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_packaging_assets", REPO_ROOT / "scripts" / "check_packaging_assets.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _png(path: Path, width: int, height: int) -> None:
    """Write a solid PNG of exactly `width` x `height`, with no Pillow."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes((200, 60, 60)) * width
    body = zlib.compress(row * height)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", body) + chunk(b"IEND", b"")
    )


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * 100)


def test_the_repository_assets_pass(tmp_path: Path) -> None:
    """CA-107.2: the current resources produce no false positive."""
    assert _checker().problems(REPO_ROOT) == []


def test_a_png_of_invalid_resolution_is_reported(tmp_path: Path) -> None:
    """CA-107.1: the 1x1 placeholder that broke v0.1.2 is caught by name.

    A 1x1 PNG is a perfectly valid image and linuxdeploy rejects it anyway,
    which is the whole reason dimensions are checked and not just format.
    """
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    _png(assets / "tray_icon.png", 1, 1)
    for name in ("critical.wav", "warning.wav", "info.wav"):
        _wav(assets / name)
    (assets / "countries.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    reported = checker.problems(tmp_path, checker.REQUIRED)

    assert len(reported) == 1
    assert "tray_icon.png" in reported[0]
    assert "1x1" in reported[0]


def test_a_file_that_is_not_a_png_is_reported(tmp_path: Path) -> None:
    """CA-107.1: the invalid placeholder that broke v0.1.1 is caught by name."""
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    (assets / "tray_icon.png").write_bytes(b"not a png at all")

    reported = checker.problems(tmp_path)

    assert any("tray_icon.png" in problem for problem in reported)


def test_a_missing_asset_is_reported(tmp_path: Path) -> None:
    """CA-107.1: an asset the spec bundles but the tree lacks stops the build."""
    checker = _checker()
    (tmp_path / "src" / "vigia_eew" / "assets").mkdir(parents=True)

    reported = checker.problems(tmp_path)

    assert any("critical.wav" in problem for problem in reported)


def test_a_truncated_sound_is_reported(tmp_path: Path) -> None:
    """CA-107.1: a sound that is not readable audio is caught before packaging.

    `sound.py` opens these at alert time. A corrupt one is silence exactly
    when the product is supposed to be impossible to ignore.
    """
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    _png(assets / "tray_icon.png", 64, 64)
    (assets / "critical.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEjunk")
    for name in ("warning.wav", "info.wav"):
        _wav(assets / name)
    (assets / "countries.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    reported = checker.problems(tmp_path)

    assert any("critical.wav" in problem for problem in reported)


def test_no_binary_is_published_without_being_run() -> None:
    """CA-107.3/CA-107.4: every packaging job runs what it just built.

    Two releases shipped broken on a resource that only went missing at
    runtime (`bdc2a9d`). Nothing noticed, because nothing in the build ever
    ran the thing the build had made.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
    # Jobs are the only two-space top-level keys under `jobs:`.
    blocks = re.split(r"^  (?=\w[\w-]*:$)", workflow, flags=re.M)
    packaging = {
        name: block
        for block in blocks
        for name in ("windows", "macos", "linux")
        if block.startswith(f"{name}:")
    }
    assert set(packaging) == {"windows", "macos", "linux"}
    for name, block in packaging.items():
        assert "smoke_binary.sh" in block, f"no smoke in the {name} job"


def test_the_acknowledgement_half_runs_where_it_can() -> None:
    """The full check needs a keystroke driven into the alert.

    Only the Linux job can do that unattended: on hosted macOS and Windows
    runners, injecting a key into another application needs permissions CI
    does not have. The other two still catch a binary that cannot start,
    which is the failure that actually shipped.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
    assert workflow.count("--acknowledge") == 1
    assert "xvfb-run -a ./scripts/smoke_binary.sh --acknowledge" in workflow


def _job(name: str) -> str:
    workflow = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
    for block in re.split(r"^  (?=\w[\w-]*:$)", workflow, flags=re.M):
        if block.startswith(f"{name}:"):
            return block
    raise AssertionError(f"no {name} job in build.yml")


def test_the_linux_binary_declares_its_base() -> None:
    """CA-107.5: an explicit, versioned base, not the runner's default.

    A PyInstaller binary links against the glibc of the machine that built
    it, and that becomes the oldest distribution it will run on. With
    `ubuntu-latest` that floor moves the day GitHub rolls the label, without
    a commit, a release note, or any way to notice except a user's bug
    report.
    """
    job = _job("linux")
    assert "ubuntu-latest" not in job, "the Linux build still follows the runner's default"
    assert re.search(r"container:|ubuntu-\d\d\.\d\d", job), "no versioned base declared"


def test_the_declared_base_is_pinned_by_digest_or_version() -> None:
    """CA-107.6: re-running the build does not move the compatibility floor."""
    job = _job("linux")
    assert re.search(r"ubuntu-\d\d\.\d\d", job), "the base carries no version"


# --- Launcher assets: the desktop entry and the icons it names (T-150) ---


def _desktop(path: Path, *, icon: str = "vigia-eew", actions: str = "Settings;") -> None:
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Vigía-eew\n"
        "Exec=vigia-eew\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=System;Monitor;\n"
        f"Actions={actions}\n"
        "\n"
        "[Desktop Action Settings]\n"
        "Name=Settings\n"
        "Exec=vigia-eew --settings\n",
        encoding="utf-8",
    )


def test_the_desktop_entry_in_the_repository_is_valid() -> None:
    """The entry ships as a file, not as a heredoc inside the build script."""
    checker = _checker()
    assert checker.desktop_problem(REPO_ROOT / "packaging" / "vigia-eew.desktop") is None


def test_an_entry_without_the_required_keys_is_reported(tmp_path: Path) -> None:
    """A desktop file missing `Exec` installs fine and launches nothing."""
    checker = _checker()
    path = tmp_path / "vigia-eew.desktop"
    path.write_text("[Desktop Entry]\nType=Application\nName=Vigía-eew\n", encoding="utf-8")

    problem = checker.desktop_problem(path)

    assert problem is not None and "Exec" in problem


def test_an_entry_naming_an_icon_nobody_installs_is_reported(tmp_path: Path) -> None:
    """`Icon=` is a theme lookup: a name with no file behind it is a grey square."""
    checker = _checker()
    path = tmp_path / "vigia-eew.desktop"
    _desktop(path, icon="vigia-eew-missing")

    problem = checker.desktop_problem(path)

    assert problem is not None and "vigia-eew-missing" in problem


def test_a_declared_action_without_a_group_is_reported(tmp_path: Path) -> None:
    """A declared action with nothing behind it is a menu item that does nothing.

    The Settings action is the one door into the configuration on a session
    where the tray menu never opens; losing it silently is the bug this
    packaging work exists to close.
    """
    checker = _checker()
    path = tmp_path / "vigia-eew.desktop"
    _desktop(path, actions="Settings;History;")

    problem = checker.desktop_problem(path)

    assert problem is not None and "History" in problem


def test_the_repository_icon_set_is_complete_and_valid() -> None:
    """Every size the packagers install, plus the .ico and .icns, in one check."""
    assert _checker().problems(REPO_ROOT) == []


def test_a_truncated_ico_is_reported(tmp_path: Path) -> None:
    checker = _checker()
    path = tmp_path / "icon.ico"
    path.write_bytes(b"\x00\x00\x01\x00\x07\x00")  # header promising 7 images, carrying none

    assert checker.ico_problem(path) is not None


def test_an_icns_that_lies_about_its_length_is_reported(tmp_path: Path) -> None:
    checker = _checker()
    path = tmp_path / "icon.icns"
    path.write_bytes(b"icns" + struct.pack(">I", 999999) + b"ic07" + struct.pack(">I", 8))

    assert checker.icns_problem(path) is not None


# --- What the three packagers actually install (T-150) ---

PACKAGING = REPO_ROOT / "packaging"


def test_every_build_script_runs_the_asset_gate() -> None:
    """CI gates on the resources; a local build did not, and shipped without them.

    The v1.0.0 `.deb` was built on a developer machine, where nothing ran
    `check_packaging_assets.py`, and installed a binary with no desktop entry
    behind it.
    """
    for script in ("build_linux.sh", "build_macos.sh", "build_windows.ps1"):
        assert "check_packaging_assets.py" in (PACKAGING / script).read_text(encoding="utf-8"), (
            f"{script} packages without validating what it packages"
        )


def test_the_linux_packages_install_the_entry_and_the_icons() -> None:
    """A binary in /usr/bin is not an application: nothing shows it to the user."""
    script = (PACKAGING / "build_linux.sh").read_text(encoding="utf-8")
    assert "/usr/share/applications/vigia-eew.desktop" in script
    assert "usr/share/icons/hicolor/" in script
    assert "scalable/apps/vigia-eew.svg" in script
    assert "MAPEOS_FPM" in script, "the .rpm path installs a bare binary again"


def test_the_deb_refreshes_the_caches_it_invalidates() -> None:
    """An entry copied into place is invisible until the two caches are rebuilt."""
    script = (PACKAGING / "build_linux.sh").read_text(encoding="utf-8")
    assert "update-desktop-database" in script
    assert "gtk-update-icon-cache" in script
    assert "postinst" in script and "postrm" in script


def test_the_appimage_uses_the_repository_entry_not_one_of_its_own() -> None:
    """One mark, one entry: the heredoc and its generated placeholder are gone."""
    script = (PACKAGING / "build_linux.sh").read_text(encoding="utf-8")
    assert "[Desktop Entry]" not in script, "the build script draws its own entry again"
    assert 'install -Dm 0644 "$RAIZ/packaging/vigia-eew.desktop" "$APPDIR/vigia-eew.desktop"' in (
        script
    )


def test_the_spec_embeds_an_icon_on_the_platforms_that_carry_one() -> None:
    spec = (PACKAGING / "vigia-eew.spec").read_text(encoding="utf-8")
    assert 'icon=_ICO if sys.platform == "win32" else None' in spec
    assert "icon=_ICNS" in spec
    assert "CFBundleShortVersionString" in spec, "the bundle ships with no version"


def test_the_windows_installer_offers_a_way_into_the_configuration() -> None:
    """The Start Menu shortcut with `--settings` is the Windows desktop action."""
    iss = (PACKAGING / "vigia-eew.iss").read_text(encoding="utf-8")
    assert 'Parameters: "--settings"' in iss
    assert "[Icons]" in iss and "{group}" in iss
    assert "--uninstall-autostart" in iss, "uninstalling leaves the scheduled task behind"


def test_the_windows_job_installs_the_compiler_the_installer_needs() -> None:
    """Without ISCC the script skips the installer and does not fail; CI must not."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    job = _job("windows")
    assert "innosetup" in job.lower()
    assert "vigia-eew-*-setup.exe" in workflow, "the installer is built and never published"


def test_the_configuration_has_a_launcher_entry_of_its_own() -> None:
    """The action is hidden behind a right-click; this one is visible and searchable."""
    entry = (PACKAGING / "vigia-eew-settings.desktop").read_text(encoding="utf-8")
    assert "Exec=vigia-eew --settings" in entry
    assert "Name[es]=Vigía-eew — Configuración" in entry
    script = (PACKAGING / "build_linux.sh").read_text(encoding="utf-8")
    assert "/usr/share/applications/vigia-eew-settings.desktop" in script


def test_the_desktop_entry_carries_the_settings_action() -> None:
    """The action the launcher shows on right-click, and what GNOME search finds."""
    entry = (PACKAGING / "vigia-eew.desktop").read_text(encoding="utf-8")
    assert "Actions=" in entry
    assert "[Desktop Action Settings]" in entry
    assert "Exec=vigia-eew --settings" in entry
