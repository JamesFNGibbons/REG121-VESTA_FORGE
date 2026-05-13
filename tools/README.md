# REG121 component ingestion CLI

The supported workflow is **Docker + `./121`** (see [README.md](../README.md) in the repo root). Each `./121 …` invocation uses `docker compose run --rm`. After updating this repo, run **`./121 build`** so the image includes the latest `tools/` (stale images can show old errors, e.g. references to removed env vars).

Ingestion prints a **Rich progress bar** (spinner + bar + % + M of N + elapsed + ETA) and updates the **current step** (checking, HTML load, Qwen enrich, embeddings, Qdrant) while each component runs, so long LLM or embedding calls stay visible.

## CLI (inside the container)

```bash
python -m tools.ingest_components library configure   # interactive (also via ./121 library configure)
python -m tools.ingest_components library status

python -m tools.ingest_components ingest --all
python -m tools.ingest_components ingest --interactive   # Questionary TUI
python -m tools.ingest_components ingest --category hero
python -m tools.ingest_components ingest --id heroes/split-left
python -m tools.ingest_components ingest --all --dry-run
python -m tools.ingest_components ingest --all --force

python -m tools.ingest_components ingest --all --handler hyperui
python -m tools.ingest_components handlers
python -m tools.ingest_components dry-run --handler hyperui
python -m tools.ingest_components classify --inbox   # stub only

python -m tools.ingest_components stats
python -m tools.ingest_components search --query "law firm hero" --category hero
python -m tools.ingest_components validate
```

### Regenerate HyperUI `catalogue.py` from disk

After copying or updating HTML under `import_bin/hyperui/`, rebuild `catalogue.py` so every `*.html` has a row (directory-derived `category`, minimal metadata; names come from Qwen on ingest):

```bash
python -m tools.generate_hyperui_catalogue
python -m tools.generate_hyperui_catalogue --library-root /absolute/path/to/hyperui
python -m tools.generate_hyperui_catalogue --dry-run   # count only, no write
```

Or from the repo root (Docker uses a **writable** bind at `/work` inside the container so `catalogue.py` can be written; the usual `/library` mount stays read-only):

```bash
./121 handler generate hyperui
./121 handler generate hyperui --dry-run
```

## Component library

- **Default:** [`import_bin/`](../import_bin/) in this repository (mounted read-only at `/library` in Docker). It is populated from `examples/component-library-starter/` so ingest works without extra setup.
- **Override:** set `HOST_COMPONENT_LIBRARY` to an absolute path, or run `./121 library configure` (writes `.reg121/component_library_root`; `./121` exports it for Compose).

## Environment variables

See [`.env.example`](../.env.example) in the repo root. Key variables:

| Variable | Purpose |
|----------|---------|
| `QDRANT_URL`, `QDRANT_API_KEY` | Qdrant Cloud |
| `QDRANT_COLLECTION_NAME` | Default `reg121_design_brain` |
| `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_INSPECTOR_MODEL`, `LITELLM_EMBEDDING_MODEL` | LiteLLM for **chat** (Qwen enrichment) and **dense embeddings** (`/v1/embeddings`). Both model ids must match exact `id` values from `GET …/v1/models` for your key; `./121 validate` checks them. |
| `DENSE_VECTOR_SIZE` | Dense vector width; must match the embedding model (default **4096** for `qwen3-embedding-8b` full output). |
| `FORGE_DEFAULT_HANDLER` | Preprocessor when `--handler` and per-entry `handler` are unset. **Default is `hyperui`.** Set to `generic` for unknown libraries. |
| `HOST_COMPONENT_LIBRARY` | Optional. Host path bind-mounted to `/library` (defaults to `./import_bin` in Compose) |

### Forge handlers (`tools/handlers/`)

- **`ingest --handler <id>`** — `hyperui`, `flowbite`, `preline`, `meraki`, `generic`. Overrides catalogue `handler` and `FORGE_DEFAULT_HANDLER`.
- **`handlers`** — Rich table of handlers, implementation row (**stub — uses generic preprocessor** for Flowbite/Preline/Meraki), and **ingested** counts from Qdrant payload `forge_handler`.
- **`dry-run`** — Multi-step diagnostic (not the same as **`ingest --dry-run`**, which skips Qdrant writes only). Exercises preprocess matrix, one Qwen enrichment, embeddings, and Qdrant connectivity.
- **Catalogue** — optional per-entry `"handler": "hyperui"` overrides CLI default for that component only.
- **Payload** — `forge_handler` is stored on upsert. **`html_raw`** holds capped raw HTML (**10_000** chars) for debugging preprocessor output; **TODO: remove or make configurable post-launch.**

HTML sent to the inspector is truncated to **4000 characters** (after preprocessing).

Every ingest run calls **LiteLLM** for Qwen enrichment and for dense embeddings (no separate embedding host).

## Qdrant collection

Named vectors `dense` (default **4096** dims for `qwen3-embedding-8b` via LiteLLM, cosine; set `DENSE_VECTOR_SIZE` to match your gateway’s embedding output) and `sparse` (SPLADE, `on_disk=false`). Payload indexes as implemented in `qdrant_wrapper.py`.

**Existing collections** created with a different dense size (e.g. 2560) must use a new `QDRANT_COLLECTION_NAME` (or recreate the collection) when switching embedding models or `DENSE_VECTOR_SIZE`.

## HyperUI and licensing

Patterns align with [HyperUI](https://www.hyperui.dev/). Starter files live under `examples/component-library-starter/` with MIT `LICENSE` and attribution. REG121 is not affiliated with HyperUI.
