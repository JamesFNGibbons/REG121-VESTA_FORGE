# REG121 AI — Component vectoriser

Ingest Tailwind-style UI components into **Qdrant Cloud** with hybrid embeddings (OpenAI dense + SPLADE sparse) and optional **Qwen** enrichment via **LiteLLM**.

## Docker-first workflow

1. Copy the starter library **out of this repository** (it is not tracked as your live library):

   ```bash
   cp -R examples/component-library-starter ~/reg121-component-library
   ```

2. Configure keys and start the stack:

   ```bash
   cp .env.example .env
   # edit .env

   chmod +x ./121
   ./121 library configure   # interactive Questionary wizard; saves .reg121/component_library_root
   ./121 up                    # build Docker images
   ./121 validate
   ./121 ingest --interactive
   ```

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
| [`examples/component-library-starter/`](examples/component-library-starter/) | **Template only** — copy elsewhere and point `./121 library configure` at it |

## Documentation

See [`tools/README.md`](tools/README.md) for CLI flags, payload schema, and HyperUI attribution.
