# Oral discussion: five-minute demonstration and likely questions

## Suggested live sequence

1. **Show two browsers:** Cesena `http://127.0.0.1:5001`, Forlì `http://127.0.0.1:5002`. Explain: two Flask services, two separate SQLite files; no central DB.
2. **Create + synchronize:** create an item on Cesena, click *Synchronize now*, and refresh Forlì.
3. **Simulate failure:** click *Simulate disconnection* on both nodes. Show that `POST /api/sync` fails but local registrations and edits continue. This models network-partitioned availability.
4. **Create incompatible changes:** edit the same report differently at both nodes, then restore the link and sync. The easiest reliable version is `python -m scripts.demo` for the full scenario.
5. **Resolve:** display both candidate versions and their vector clocks, select one using *Keep this version*, synchronize again and show convergence.
6. **Differentiate matching:** show a LOST item and a separately created FOUND item as a possible keyword match, not a version conflict.

## Short verbal explanations (English)

**Why is it distributed?** “The application has two independently running processes and two separate local databases. They exchange data over HTTP, rather than reading one shared database.”

**What happens during a network failure?** “Both nodes can still accept local changes. Their data may temporarily differ because synchronization is unavailable.”

**What is eventual consistency?** “If new writes stop, the network is restored, and synchronization succeeds, both nodes eventually receive the same versions. Concurrent updates require an explicit resolution before a single current state is available.”

**Why vector clocks?** “A timestamp only says when something was written according to a local clock. Vector clocks let us detect whether an edit causally follows another or whether two edits occurred independently.”

**What is the CAP trade-off here?** “During a network partition we prefer to accept local writes, even though the nodes cannot guarantee an immediately identical view. We later synchronize and resolve divergence.”

**What is REST?** “The nodes expose HTTP endpoints for creating, reading and updating reports, and an endpoint for exchanging JSON report versions.”

**What is the difference between matching and a conflict?** “A match suggests that two different reports may describe the same real-world item. A conflict means two concurrent versions of one report have incompatible edit histories.”

**What is not implemented?** “No background synchronization, authentication or production-grade deployment; and full history exchange is not optimized for large-scale workloads.”

## Important demonstrations to rehearse

- Explain `{cesena: 2}` versus `{cesena: 1, forli: 1}`: neither dominates the other.
- Explain how merging yields `{cesena: 3, forli: 1}` after a Cesena resolution.
- Be able to show the role of `campus/core.py` versus `campus/server.py`.
- Don't claim that the simulation literally disconnects your Wi-Fi; it disables *replication* between the two local processes.
