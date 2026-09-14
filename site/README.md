# Static website and GitHub Pages

[English project guide](../README.en.md) | [Guia del proyecto en espanol](../README.md)

The website is a bilingual, self-contained HTML artifact generated from the
reviewed Markdown guides and the documentary configuration profile. It includes
the complete guides in a searchable reader, not just links to raw Markdown.
Linked public scripts and configuration examples are embedded for inspection
and download. No live Halo Strix endpoint, analytics, CDN or external font is used.

## Build locally

Requirements: Python **3.12+**, pip and the pinned build dependency in
[`requirements.txt`](requirements.txt). No Node.js or frontend bundler is needed.
From the repository root on Windows:

```powershell
python -m venv .venv-site
.\.venv-site\Scripts\python.exe -m pip install -r .\site\requirements.txt
.\.venv-site\Scripts\python.exe .\scripts\build_site.py
```

On Linux/macOS, from the repository root:

```bash
python3 -m venv .venv-site
.venv-site/bin/python -m pip install -r site/requirements.txt
.venv-site/bin/python scripts/build_site.py
```

Open `site/dist/index.html` directly, or serve only the generated output:

```powershell
.\.venv-site\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory .\site\dist
```

Then open `http://localhost:8000`. The server is only a local preview; stop it
when finished. Do not serve the repository root, which contains ignored
private files. The generated page also works beneath a project path such as
`/repository/`, without hardcoded root URLs.

Optional URL settings: `?lang=en` or `?lang=es`, and
`?scoutTheme=dark` or `?scoutTheme=light`. Documentation deep links use the
URL hash, so no server-side routing is required.

## Deploy using GitHub Pages

The workflow is [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).
It builds the page and uploads **only `site/dist`**, never the entire checkout.

1. Publish the reviewed repository files through Git. Keep ignored local
   credentials, agent state, datasets and model weights out of the commit.
2. On GitHub, open **Settings > Pages > Build and deployment** and set
   **Source** to **GitHub Actions**.
3. Push to `main` or `master`, or run **Actions > Deploy static site > Run
   workflow** manually. Adjust the branch list if your publishing branch differs.
4. Wait for the build and deployment jobs. GitHub displays the actual URL in
   the `github-pages` environment and Pages settings.

The workflow needs Pages enabled for the repository and a plan/visibility
combination that supports Pages. It uses GitHub's deployment token with
`pages: write` and `id-token: write`; do not add a personal access token.
The `github-pages` environment must allow the publishing branch.

This guide does not assert that a repository or public site has already been
created. Do not infer a public URL from a local build. Publishing the website
does not expose Lemonade, LlamaBoard or Studio to the Internet.

## Content and maintenance

- Edit the existing Markdown guides, workspace READMEs and
  [`halo-strix.reference.json`](../config/halo-strix.reference.json), then rebuild.
- Edit [`index.template.html`](index.template.html) for presentation and interaction.
- The builder embeds root project guides, `docs/`, workspace Markdown guides,
  the script manual and this deployment manual, plus approved linked source files.
- Raw Markdown HTML is escaped. Relative links become reader routes; private
  environment files, runtime-data directories and symlinks/junctions are rejected.
- `site/dist/` and `.venv-site/` are ignored. Do not edit the generated page by hand.
- The output directory may contain only `index.html` and `.nojekyll`; unexpected
  files cause a build failure instead of being silently deployed.

Keep the reference date and pending incidents accurate. This site displays a
historical configuration, not live telemetry or an assurance of current health.

## Build regression checks

With the build dependency installed:

```powershell
.\.venv-site\Scripts\python.exe -m unittest discover -s .\scripts\tests -p test_build_site.py -v
```

The tests invoke the builder's CLI with isolated fixtures and check document
inclusion, safe embedding, rewritten links, source exclusions and deterministic
output. They do not contact the Halo server or start any model/container.

For browser checks, install the separate
[`requirements-browser.txt`](requirements-browser.txt) in the same environment
and use an already installed, approved Edge browser:

```powershell
.\.venv-site\Scripts\python.exe -m pip install -r .\site\requirements-browser.txt
.\.venv-site\Scripts\python.exe .\scripts\tests\test_site_browser.py --browser-channel msedge -v
```

These checks start a temporary loopback server and an isolated headless browser,
exercise language/theme/model controls, the complete reader, filters, downloads,
copy feedback and mobile layouts, then close both. No browser is downloaded,
no execution policy is bypassed, and no system clipboard is changed.
The Pages build job runs the dependency-light builder tests; browser checks are
an additional local check, not claimed as part of that workflow.

## Resumen en espanol

Genera la web con `scripts\build_site.py` despues de instalar la dependencia
en el entorno aislado. El resultado es `site\dist\index.html`, con portada
bilingue y lector de guias completas. Para publicarla, selecciona
**Settings > Pages > Source: GitHub Actions** y ejecuta el workflow incluido.
Se sube solo `site\dist`, no la carpeta del repositorio ni los servicios del Halo.
