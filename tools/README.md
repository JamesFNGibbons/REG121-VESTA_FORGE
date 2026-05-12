# REG121 component ingestion CLI

The supported workflow is **Docker + `./121`** (see [README.md](../README.md) in the repo root). Each `./121 …` invocation uses `docker compose run --rm`.

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
| `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_INSPECTOR_MODEL` | LiteLLM for enrichment (Qwen) only. **`LITELLM_INSPECTOR_MODEL` must be an exact `id` from `GET …/v1/models`** for your key; `./121 validate` warns if it is missing from that list. |
| `DEEPINFRA_API_KEY`, `DEEPINFRA_BASE_URL`, `DEEPINFRA_EMBEDDING_MODEL`, `DENSE_VECTOR_SIZE` | [DeepInfra](https://deepinfra.com/docs/openai_api) OpenAI-compatible API for dense vectors; `DENSE_VECTOR_SIZE` must match the model (default **2560** for `Qwen/Qwen3-Embedding-4B`) |
| `FORGE_DEFAULT_HANDLER` | Preprocessor when `--handler` and per-entry `handler` are unset. **Default is `hyperui`.** Set to `generic` for unknown libraries. |
| `HOST_COMPONENT_LIBRARY` | Optional. Host path bind-mounted to `/library` (defaults to `./import_bin` in Compose) |

### Forge handlers (`tools/handlers/`)

- **`ingest --handler <id>`** — `hyperui`, `flowbite`, `preline`, `meraki`, `generic`. Overrides catalogue `handler` and `FORGE_DEFAULT_HANDLER`.
- **`handlers`** — Rich table of handlers, implementation row (**stub — uses generic preprocessor** for Flowbite/Preline/Meraki), and **ingested** counts from Qdrant payload `forge_handler`.
- **`dry-run`** — Multi-step diagnostic (not the same as **`ingest --dry-run`**, which skips Qdrant writes only). Exercises preprocess matrix, one Qwen enrichment, embeddings, and Qdrant connectivity.
- **Catalogue** — optional per-entry `"handler": "hyperui"` overrides CLI default for that component only.
- **Payload** — `forge_handler` is stored on upsert. **`html_raw`** holds capped raw HTML (**10_000** chars) for debugging preprocessor output; **TODO: remove or make configurable post-launch.**

HTML sent to the inspector is truncated to **4000 characters** (after preprocessing).

Every ingest run calls **LiteLLM / Qwen** enrichment before embeddings (no opt-out).

## Qdrant collection

Named vectors `dense` (default **2560** dims for `Qwen/Qwen3-Embedding-4B` on DeepInfra, cosine; set `DENSE_VECTOR_SIZE` to match the model you use) and `sparse` (SPLADE, `on_disk=false`). Payload indexes as implemented in `qdrant_wrapper.py`.

**Existing collections** created with 1536-dim OpenAI embeddings must use a new `QDRANT_COLLECTION_NAME` (or recreate the collection) when switching to Qwen3 dense vectors.

## HyperUI and licensing

Patterns align with [HyperUI](https://www.hyperui.dev/). Starter files live under `examples/component-library-starter/` with MIT `LICENSE` and attribution. REG121 is not affiliated with HyperUI.
