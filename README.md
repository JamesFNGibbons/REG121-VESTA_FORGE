# REG121 AI — Component vectoriser

Ingest Tailwind-style UI components into **Qdrant Cloud** with hybrid embeddings (**DeepInfra** dense + SPLADE sparse), optional **Qwen** enrichment via **LiteLLM**, and pluggable **Forge** HTML preprocessors (`FORGE_DEFAULT_HANDLER`, default **hyperui**; set **`FORGE_DEFAULT_HANDLER=generic`** for unknown libraries — see [`tools/README.md`](tools/README.md)).

## Docker-first workflow

1. **Component library** — by default use **`import_bin/`** in this repo (pre-populated from `examples/component-library-starter/`). Edit or replace files there, or set `HOST_COMPONENT_LIBRARY` / run `./121 library configure` to use another path.

2. Configure keys and start the stack:

   ```bash
   cp .env.example .env
   # edit .env

   chmod +x ./121
   ./121 up                    # build Docker images
   ./121 validate
   ./121 ingest --interactive   # optional; ./121 ingest --all works without the wizard
   ```

   Optional: `./121 library configure` — writes `.reg121/component_library_root` if you want a path other than `import_bin/`.

3. Day-to-day:

   ```bash
   ./121 ingest --all
   ./121 stats
   ./121 search --query "law firm hero" --category hero
   ./121 shell
   ./121 down
   ```

`./121` uses Docker Compose (`docker-compose.yml` at the repo root). Each command runs `docker compose run --rm` unless noted.

## Layout

| Path | Role |
|------|------|
| [`./121`](121) | Control script (build, up, ingest, library wizard, shell) |
| [`docker-compose.yml`](docker-compose.yml) | `app` (runtime) + `tool` (library configure wizard, no library mount) |
| [`Dockerfile`](Dockerfile) | Python 3.12 + tools + SPLADE warmup |
| [`tools/`](tools/) | CLI (`ingest_components`), pipeline, Qdrant, embeddings, inspector |
| [`import_bin/`](import_bin/) | **Default library** — `catalogue.py` + HTML (same starter content as `examples/component-library-starter/`); override mount with `HOST_COMPONENT_LIBRARY` |
| [`examples/component-library-starter/`](examples/component-library-starter/) | **Template** — reference copy; `import_bin` is seeded from here |

## Documentation

See [`tools/README.md`](tools/README.md) for CLI flags, payload schema, and HyperUI attribution.
