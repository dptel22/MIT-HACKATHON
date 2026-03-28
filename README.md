# KubeResilience Demo Repo

This repo is split into a small number of top-level areas so handoff stays simple:

- `backend/`: FastAPI orchestration, detection, decisioning, recovery, verifier, and tests
- `frontend/`: React/Vite dashboard for the live demo
- `docs/`: PRD, backend notes, and chaos-engine reference material
- `data/`: local runtime state only; not source-of-truth application code

## Intended source-of-truth layout

```text
MIT/
|-- backend/
|   |-- chaos/
|   |-- models/
|   |-- main.py
|   |-- detector.py
|   |-- decision.py
|   |-- recovery.py
|   |-- verifier.py
|   `-- test_*.py
|-- frontend/
|   |-- public/
|   |-- src/
|   |-- package.json
|   `-- vite.config.js
|-- docs/
|   |-- backend/
|   `-- reference/
`-- data/
```

## Notes

- Runtime databases, caches, logs, local virtualenvs, and kubeconfig are intentionally ignored.
- Historical docs that used to live under `backend/` are now expected to live under `docs/`.
- The repository should be shared from source files, not from local generated artifacts.
