# Procedimiento de release — Vigía-eew

Versionado semántico (`MAYOR.MENOR.PARCHE`, RF-27). Cada release parte de `develop` con el
gate de calidad en verde (`pytest`, `ruff check .`, `mypy src`).

`main` está **protegida**: no se puede pushear directo (ni siquiera admins) y todo cambio
entra por PR con los checks `ci` (ruff/mypy/pytest) y `security` (bandit/semgrep/pip-audit/
gitleaks/trivy) en verde. Por eso el release se corta **en `develop` y se promueve por PR**:

1. En `develop`: actualizar `version` en `pyproject.toml` y mover la sección `[Sin publicar]`
   de `CHANGELOG.md` a una nueva `## [X.Y.Z] - AAAA-MM-DD`. Commitear `chore: release vX.Y.Z`
   y `git push origin develop`.
2. Abrir el PR `develop → main` (`gh pr create --base main --head develop …`). Esperar a que
   `ci` + `security` pasen y **mergear** el PR (los tags no están protegidos, pero el commit de
   release sí debe llegar a `main` por esta vía).
3. Traer `main` y taguear el commit ya en `main`:
   `git checkout main && git pull origin main && git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
4. El push del tag dispara `.github/workflows/build.yml` (F8-5): construye wheel/sdist
   (F8-1), el `.exe` de Windows (F8-2), el `.app`/`.dmg` de macOS (F8-3) y el
   AppImage/`.deb`/`.rpm` de Linux (F8-4); publica todo como *assets* de un GitHub Release
   con el mismo tag.
5. Publicar en PyPI: tras construirse **todos** los paquetes (wheel/sdist + los binarios
   nativos), el job `publish-pypi` descarga el wheel/sdist y lo publica en PyPI con
   `uv publish`, usando el secreto del repositorio `PYPI_API_TOKEN`. Si el secreto no está
   configurado (p. ej. en un *dispatch* manual desde un *fork*), el paso se omite sin fallar
   y `dist/*.whl`/`dist/*.tar.gz` quedan igual disponibles como *assets* del Release para
   publicar manualmente con `uv publish` o `twine upload`.
6. Actualizar el repo apt (F8-6, ver `packaging/apt-r2/README.md`) con el nuevo `.deb`.

## Verificación local antes de taguear

```bash
uv build                                  # F8-1: wheel + sdist
uv pip install --python /tmp/venv dist/*.whl   # instala en un venv limpio
vigia-eew --check-config                  # smoke test del entry point
```

`packaging/build_linux.sh` (y `_windows.ps1`/`_macos.sh` en su SO respectivo) hacen el
mismo build que CI para los binarios nativos; ver los requisitos de herramientas en la
cabecera de cada script.
