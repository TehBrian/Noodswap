# Data Layout

- `data/seeds/`: versioned seed assets used to initialize fresh runtime state.
- `data/testdata/`: versioned fixtures reserved for tests and local experiments.
- `runtime/`: mutable live state and caches (not committed).

Recommended flow:

1. Commit seed fixtures under `data/seeds/`.
2. Initialize `runtime/` from seeds via `scripts/init_runtime.py`.
3. Run the bot against `runtime/` paths only.
