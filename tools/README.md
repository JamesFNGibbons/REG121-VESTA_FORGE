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

## Component library (outside this repo)

- Copy [`examples/component-library-starter/`](../examples/component-library-starter/) to any directory on your machine.
- Run `./121 library configure` and confirm the path (or set `HOST_COMPONENT_LIBRARY` / write `.reg121/component_library_root`).
- In Docker, the library is mounted read-only at `/library`; `COMPONENT_LIBRARY_ROOT` is set to `/library`.

## Environment variables

See [`.env.example`](../.env.example) in the repo root. Key variables:

| Variable | Purpose |
|----------|---------|
| `QDRANT_URL`, `QDRANT_API_KEY` | Qdrant Cloud |
| `QDRANT_COLLECTION_NAME` | Default `reg121_design_brain` |
| `LITELLM_*`, `OPENAI_API_KEY` | As before |
| `HOST_COMPONENT_LIBRARY` | Host path bind-mounted to `/library` (Compose); optional if `.reg121/component_library_root` exists and `./121` exports it |

HTML sent to the inspector is truncated to **4000 characters**.

### `--skip-enrichment`

Skips LiteLLM / Qwen. Dense + sparse embeddings still run using catalogue-only `embedding_text` plus the UK/SMB keyword tail.

## Qdrant collection

Named vectors `dense` (1536, cosine) and `sparse` (SPLADE, `on_disk=false`). Payload indexes as implemented in `qdrant_wrapper.py`.

## HyperUI and licensing

Patterns align with [HyperUI](https://www.hyperui.dev/). Starter files live under `examples/component-library-starter/` with MIT `LICENSE` and attribution. REG121 is not affiliated with HyperUI.
