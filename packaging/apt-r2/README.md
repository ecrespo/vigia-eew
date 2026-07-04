# Repo APT en Cloudflare R2 (F8-6, RF-32)

Documentación de cómo alojar un repositorio APT mínimo para el `.deb` de Vigía-eew
(generado por `packaging/build_linux.sh`, F8-4) en **Cloudflare R2** (S3-compatible),
sin depender de un PPA de Launchpad ni de infraestructura propia. **No implementado
todavía**: no hay bucket ni pipeline de publicación configurados; esto es la guía para
cuando se decida activarlo.

## Por qué R2 y no Launchpad/un servidor propio

- Sin servidor que mantener 24/7 (RNF-02, mismo principio que "cada máquina su agente").
- Sin costo de egress en R2 (a diferencia de S3), relevante para un proyecto sin fines de lucro.
- Compatible con cualquier cliente S3 (`aws s3` / `rclone` / `s3cmd`) para publicar.

## Estructura del repositorio

```
apt.vigia-eew.example/
└── dists/stable/main/binary-amd64/
    ├── Packages          # generado por `dpkg-scanpackages` o `reprepro`
    ├── Packages.gz
    └── Release           # firmado con `gpg --clearsign` (InRelease) o detached (.gpg)
└── pool/main/v/vigia-eew/
    └── vigia-eew_X.Y.Z_amd64.deb
```

## Publicación (esbozo, `reprepro`)

```bash
# Una sola vez: crear la config del repo (conf/distributions con Origin/Codename/Components).
reprepro -b repo includedeb stable dist/vigia-eew_X.Y.Z_amd64.deb

# Subir a R2 (bucket ya creado, credenciales en variables AWS_* estándar):
aws s3 sync repo/ s3://apt-vigia-eew/ --endpoint-url "$R2_ENDPOINT"
```

La clave GPG de firma **no** vive en el repo; se genera una vez y su ID público se
documenta aquí cuando exista (`gpg --export --armor <KEYID> > vigia-eew.gpg.key`,
publicada también en el bucket para que los usuarios la importen).

## Uso desde la máquina del usuario

```bash
curl -fsSL https://apt.vigia-eew.example/vigia-eew.gpg.key | sudo tee /etc/apt/keyrings/vigia-eew.asc
echo "deb [signed-by=/etc/apt/keyrings/vigia-eew.asc] https://apt.vigia-eew.example stable main" \
    | sudo tee /etc/apt/sources.list.d/vigia-eew.list
sudo apt update && sudo apt install vigia-eew
```

## Pendiente para activarlo

- Crear el bucket R2 y un dominio público (o el endpoint `*.r2.dev`).
- Generar y resguardar la clave GPG de firma del repo.
- Automatizar el paso `reprepro`+`aws s3 sync` como job adicional de
  `.github/workflows/build.yml` (F8-5) tras publicar el Release.
