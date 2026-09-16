# Repository reference

Start with the [English documentation](docs/en/README.md) or the
[Spanish reference](docs/configuracion-reutilizable-halo-strix.md), and the
[documentary profile](config/halo-strix.reference.json).
Distinguish historical evidence, recommendations and live observations.
These files do not establish the host's current configuration or health.

Public examples must use placeholders, not private host addresses, usernames,
credentials, session identifiers or local agent state. Do not read real
environment files to populate documentation; use the reviewed `.env.example`
templates. Preserve ignored local files and never force-add them for publication.

## Documentation checks

Use the ignored `.venv-site` environment with `site/requirements.txt` installed:

```bash
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

The builder discovers Markdown under `docs/` recursively. New guides need index
links, not a hardcoded document list. A successful fixture test run does not
prove the complete site builds; run both commands and report unrelated source
publication failures without broadening the publication allowlist automatically.

The inference workspace uses `python3 -m unittest discover -s scripts/tests
-p 'test_inference*.py' -v` (run as one command). Optional tests use the pinned
binary in ignored `workspaces/inference/data/bin/llama-swap` against a synthetic
loopback backend; they do not validate GPU inference. All workspace credentials,
installed tools and generated configuration belong under its ignored `data/`.
