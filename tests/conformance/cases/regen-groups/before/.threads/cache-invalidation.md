---
id: cache-invalidation
status: open
opened: 2026-03-01
touched: 2026-03-08
question: Should the build cache be keyed on the lockfile or on the resolved tree?
leaning: The resolved tree, since two lockfiles can resolve to the same packages.
---

## 2026-03-01

Opened while profiling slow CI runs.
