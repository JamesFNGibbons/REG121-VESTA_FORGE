# import_bin

Component libraries live **per handler** under `import_bin/<handler_id>/` (e.g. `import_bin/hyperui/catalogue.py`).

Use `./121 library configure` or the **ingest interactive** wizard to pick a handler; the choice is saved under `.reg121/forge_handler` and drives which subdirectory is used when you are not using a custom `COMPONENT_LIBRARY_ROOT`.

Valid handler ids match `python -m tools.ingest_components handlers`: `hyperui`, `flowbite`, `preline`, `meraki`, `generic`.
