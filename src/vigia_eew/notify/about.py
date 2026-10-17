"""What the About window says, decided without a display (T-151).

Version, copyright, licence and the warranty notice are facts about the
build. Typed into labels by hand they go stale the release after next, and a
wrong licence line is a legal problem rather than a cosmetic one -- so the
version comes from the installed package's own metadata and the rest lives
here, next to a test that reads it.

The widget tree is `about_window.py`; this module has no UI toolkit in it.
"""

from __future__ import annotations

from dataclasses import dataclass

from vigia_eew import __version__
from vigia_eew.i18n import DEFAULT_LOCALE, t

#: SPDX identifier of the licence in `LICENSE`, and the year and holder of the
#: copyright line. Changing the file without changing these is the mismatch
#: `tests/test_about.py` exists to catch.
LICENSE_SPDX = "GPL-3.0-or-later"
COPYRIGHT_YEAR = "2026"
COPYRIGHT_HOLDER = "Ernesto Crespo"
PROJECT_URL = "https://github.com/ecrespo/vigia-eew"


@dataclass(frozen=True)
class AboutInfo:
    """Everything the About window shows, already translated."""

    name: str
    version: str
    description: str
    copyright: str
    license: str
    warranty: str
    url: str

    def rows(self) -> list[tuple[str, str]]:
        """Label/value pairs, in the order the window draws them."""
        return [
            ("", self.name),
            ("", self.description),
            (t("about_version", self._locale), self.version),
            (t("about_license", self._locale), self.license),
            ("", self.copyright),
            ("", self.warranty),
            ("", self.url),
        ]

    _locale: str = DEFAULT_LOCALE


def about_info(*, locale_code: str = DEFAULT_LOCALE) -> AboutInfo:
    """The application's own description, in `locale_code`."""
    return AboutInfo(
        name="Vigía-eew",
        version=__version__,
        description=t("about_description", locale_code),
        copyright=f"© {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}",
        license=LICENSE_SPDX,
        warranty=t("about_warranty", locale_code),
        url=PROJECT_URL,
        _locale=locale_code,
    )
