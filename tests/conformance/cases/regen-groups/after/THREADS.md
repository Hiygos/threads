# THREADS

> Generated from `.threads/`. Do not edit by hand: edit the thread files,
> and this index is rebuilt on the next upkeep.

## Open

- **[auth-token-lifetime](.threads/auth-token-lifetime.md)** — How long should a refresh token live?
- **[cache-invalidation](.threads/cache-invalidation.md)** — Should the build cache be keyed on the lockfile or on the resolved tree?
  - leaning: The resolved tree, since two lockfiles can resolve to the same packages.

## Deferred

- **[api-pagination](.threads/api-pagination.md)** — Cursor or offset pagination for the public API?
  - leaning: Cursor, but only once the v2 endpoints exist.

## Proposed (awaiting confirmation)

- **[release-cadence](.threads/release-cadence.md)** — Do we release every two weeks or when a milestone closes?
