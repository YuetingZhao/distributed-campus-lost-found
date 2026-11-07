# Architecture and Design Decisions

## Nodes and interfaces

Each node is one independently executed Flask application and one SQLite database. In the local demonstration Cesena is on `127.0.0.1:5001`; Forlì is on `127.0.0.1:5002`. No central database is shared. Both serve a browser interface, the same REST resource APIs and an internal replication API.

The `Store` class in `campus/core.py` isolates persistence and causal-version logic from the web framework. The Flask adapter in `campus/server.py` handles requests and maps `ProjectError` exceptions to HTTP errors.

## Data and write model

Each report is described by its UUID, kind (`LOST` or `FOUND`), title, description, category, originating campus, status (`OPEN` or `RESOLVED`), and timestamps.

Instead of storing one mutable row per report, each local edit creates a *new, immutable version row*. Each row contains a unique version UUID, the report UUID, its origin node, a vector clock JSON object and the complete report data JSON object. This allows multiple concurrent versions to be retained without silent data loss.

## Replication protocol

A manual request to `POST /api/sync` at node A initiates one exchange:

1. A reads its local version history.
2. A sends the history as JSON to B's `POST /api/replicate` endpoint.
3. B validates and inserts any missing versions (idempotently by version UUID).
4. B returns its entire now-updated history.
5. A inserts previously missing versions from B.
6. Both independently compute active report heads from their local histories.

With no concurrent writes during exchange, both nodes now hold the union of version histories and compute the same report views. Under subsequent independent writes, another exchange is required.

## Causality and concurrency

A version clock `A` *dominates* `B` if A has a counter at least as high for every component and a strictly higher counter in at least one component. Dominated versions are historical; incomparable maximal versions are conflicting heads. This captures the presence of concurrent changes without relying on machine wall-clock synchronization.

When conflicts are present, normal updates are rejected with `409 Conflict`, and neither candidate is discarded. The resolve operation selects one current candidate, merges all maximal clocks and increments the resolving node's component. The merged version therefore dominates all conflicting heads and becomes the sole active version after replication.

## Network partitions and failure modes

The `connected` state is persisted per campus. Setting it to false blocks outgoing and incoming *replication* requests, but does not block local database operations or normal UI/API access. To simulate a complete two-way network cut, **disable it at both nodes**. An unavailable peer also returns a `503` error to the initiating client. No partial transaction across both nodes is attempted.

The design favors local write availability over strict cross-node consistency during partitions. This is an illustration of the CAP trade-off, not a claim that an entire system has a static choice of 'AP'. Local databases retain their own durable snapshots; a full end-to-end high-availability guarantee is not demonstrated.

## Possible matches are not conflicts

A lost-item report and a found-item report are separate report UUIDs. A small token-overlap heuristic suggests pairs of titles sharing a meaningful keyword and a compatible category. This does not mutate either report or resolve identities. By contrast, conflict detection compares multiple versions of the *same* UUID.

## Constraints and possible extensions

Current design constraints: exactly two configured nodes, manual synchronization, complete history exchange, no authentication/authorization, localhost-only demonstration, no security for peer messages, no user accounts, and basic title-based suggestions. Potential future work: incremental replication, automatic retries/backoff, peer authentication, signed events, multi-node topology, improved matching, better causal metadata and persistent audit UI.
