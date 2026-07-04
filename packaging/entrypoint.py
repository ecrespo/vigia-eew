"""Punto de entrada para el binario congelado (PyInstaller, RF-28..RF-30).

`pyproject.toml` expone el entry point `vigia-eew = vigia_eew.cli:main` para instalaciones
por `pip`/PyPI (F8-1), pero PyInstaller necesita un **script**, no una referencia de
entry point de setuptools/hatchling. Este archivo es ese script: solo importa y llama a
`main()`, sin lógica propia.
"""

from __future__ import annotations

import sys

from vigia_eew.cli import main

if __name__ == "__main__":
    sys.exit(main())
