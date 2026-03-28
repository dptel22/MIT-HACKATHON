# Docs Guide

Use these docs in this order:

- `backend/prd.md`: original hackathon scope and safety intent
- `reference/chaosengine.txt`: historical chaos-engine checklist and rationale
- `backend/backend_documentation.md`: implementation notes from earlier iterations

## Important

- The current codebase is the source of truth when a doc and the code disagree.
- Chaos manifests now use `memory_leak.yaml`, not `memory_stress.yaml`.
- Warm-up is currently skipped in code because the repository ships with precomputed baselines.
