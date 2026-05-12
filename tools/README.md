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
python -m tools.ingest_components ingest --all --skip-enrichment

python -m tools.ingest_components stats
python -m tools.ingest_components search --query "law firm hero" --category hero
python -m tools.ingest_components validate
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
| `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_INSPECTOR_MODEL` | LiteLLM for enrichment (Qwen) only |
| `DEEPINFRA_API_KEY`, `DEEPINFRA_BASE_URL`, `DEEPINFRA_EMBEDDING_MODEL`, `DENSE_VECTOR_SIZE` | [DeepInfra](https://deepinfra.com/docs/openai_api) OpenAI-compatible API for dense vectors; `DENSE_VECTOR_SIZE` must match the model (default **2560** for `Qwen/Qwen3-Embedding-4B`) |
| `HOST_COMPONENT_LIBRARY` | Optional. Host path bind-mounted to `/library` (defaults to `./import_bin` in Compose) |

HTML sent to the inspector is truncated to **4000 characters**.

### `--skip-enrichment`

Skips LiteLLM / Qwen. Dense + sparse embeddings still run using catalogue-only `embedding_text` plus the UK/SMB keyword tail.

## Qdrant collection

Named vectors `dense` (default **2560** dims for `Qwen/Qwen3-Embedding-4B` on DeepInfra, cosine; set `DENSE_VECTOR_SIZE` to match the model you use) and `sparse` (SPLADE, `on_disk=false`). Payload indexes as implemented in `qdrant_wrapper.py`.

**Existing collections** created with 1536-dim OpenAI embeddings must use a new `QDRANT_COLLECTION_NAME` (or recreate the collection) when switching to Qwen3 dense vectors.

## HyperUI and licensing

Patterns align with [HyperUI](https://www.hyperui.dev/). Starter files live under `examples/component-library-starter/` with MIT `LICENSE` and attribution. REG121 is not affiliated with HyperUI.
