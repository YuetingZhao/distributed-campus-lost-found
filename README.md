# Distributed Campus Lost & Found

**Distributed Systems — University of Bologna | Coursework prototype**

A small, two-node lost-and-found web application for the fictional **Cesena** and **Forlì** university campus locations. Each node uses a separate Flask process and local SQLite database. Reports can be created and updated independently while the two campuses are disconnected, then synchronized over HTTP/JSON when connectivity returns.

This project is an **educational prototype**, designed to demonstrate distributed architecture, replication, network partitions, eventual convergence and causally concurrent edit detection using **vector clocks**. It is **not** a production-ready public website.

## Features

- Two independently running campus nodes, with **separate SQLite files** and a browser-based dashboard.
- Create lost and found reports, browse/search them, and mark reports as resolved.
- Two-way report synchronization with a REST API (`POST /api/sync`).
- Simulated link outage; each campus stays writable locally even when synchronization fails.
- Conflict detection when the **same report** is edited independently at both nodes during a partition.
- Explicit human conflict resolution with causal merge; the losing version stays in the immutable history.
- Simple **possible matches** between *different* lost and found reports (keyword suggestion, not the same as an edit conflict).
- A repeatable automated demo and unit/integration tests.

## Architecture

```text
   Browser A                            Browser B
      |                                    |
      v                                    v
+------------------------+   REST/JSON   +------------------------+
| Cesena node            |<------------->| Forli node             |
| Flask on :5001         |   /api/sync   | Flask on :5002         |
|                        |               |                        |
| SQLite: cesena.sqlite3 |               | SQLite: forli.sqlite3  |
+------------------------+               +------------------------+

     Local writes continue independently during a network partition.
```

All processes run on your **own computer** using two different localhost ports; no remote hosting or campus network access is required.

## Quick start (macOS, Linux, Windows PowerShell alternative)

Prerequisite: **Python 3.10 or later**.

```bash
# From the project folder (where requirements.txt lives):
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Fastest option: start both independent node processes from **one terminal**:

```bash
python -m scripts.run_both
```

Or open **two terminals**, each inside the project folder:

```bash
# Terminal 1: Cesena
python -m scripts.run_cesena
```

```bash
# Terminal 2: Forlì
python -m scripts.run_forli
```

Open the two dashboards (with either startup method):

- **Cesena:** http://127.0.0.1:5001
- **Forlì:** http://127.0.0.1:5002

Windows PowerShell: activate the environment using `.venv\Scripts\Activate.ps1`, then use the same `python -m ...` commands.

> **Important:** The app provides intentionally unauthenticated demonstration endpoints to switch connectivity and resolve conflicts. It binds to `127.0.0.1` only. **Do not deploy it to the public Internet.**

## Demonstration (recommended for oral discussion)

With both node servers running, use a **third terminal**:

```bash
python -m scripts.demo
```

This script exercises the complete distributed scenario:

1. Create a lost-item report in Cesena and synchronize it to Forlì.
2. Disable inter-node connectivity for **both** nodes.
3. Edit the **same report differently** at both campuses; independently create a found-item report in Forlì.
4. Confirm each campus can still write locally and synchronization fails during the outage.
5. Restore connectivity and synchronize the two databases.
6. Detect two causally concurrent versions as a **conflict** (without silently overwriting either).
7. Choose a version to resolve the conflict, then synchronize the merged result.
8. Display a possible lost/found match as a *separate* matching feature.

Each run creates new sample records; to reset all demonstration data, stop both servers, delete `data/cesena.sqlite3*` and `data/forli.sqlite3*`, and restart. **Deleting these files permanently removes local data.**

### Manual demo in the browser

Create an item on the Cesena dashboard → click **Synchronize now** → verify it appears in Forlì. Click **Simulate disconnection** in **both** dashboards. Update the same report in different ways (the UI offers *Mark resolved*; for more nuanced edits, use the automated demo or the REST API). Restore both connections, synchronize, and choose a version on the conflict card. Synchronize again to propagate the resolution.

## API reference

All endpoints accept/return JSON except the `/` web page.

| Method | Endpoint | Purpose |
|:--|:--|:--|
| `GET` | `/api/health` | Node identity, link simulation state, record statistics |
| `GET` | `/api/items` | Current report views (or all concurrent candidates) |
| `POST` | `/api/items` | Create a new local report |
| `GET` | `/api/items/<id>` | Read one report |
| `PATCH` | `/api/items/<id>` | Change title, description, category or status |
| `POST` | `/api/items/<id>/resolve` | Select a current candidate and causally merge all heads |
| `GET` | `/api/matches` | Suggest pairs of distinct lost/found reports |
| `POST` | `/api/sync` | Synchronize with the configured peer |
| `POST` | `/api/replicate` | Peer-to-peer version exchange (internal endpoint) |
| `GET` | `/api/admin/network` | Read the simulated connectivity state |
| `PUT` | `/api/admin/network` | Enable/disable simulated node-to-node connectivity |

Example: create a lost-item report on Cesena (Terminal 3):

```bash
curl -X POST http://127.0.0.1:5001/api/items \
  -H 'Content-Type: application/json' \
  -d '{"kind":"LOST","title":"Black MacBook charger","category":"electronics","description":"Cesena library"}'
```

Exchange changes:

```bash
curl -X POST http://127.0.0.1:5001/api/sync
```

Simulate a network outage **on both nodes**:

```bash
curl -X PUT http://127.0.0.1:5001/api/admin/network -H 'Content-Type: application/json' -d '{"connected":false}'
curl -X PUT http://127.0.0.1:5002/api/admin/network -H 'Content-Type: application/json' -d '{"connected":false}'
```

Restore connectivity with `true` instead of `false`, then call `/api/sync`.

## How conflicts work

Every mutation creates an **immutable snapshot** with a vector clock. Each local write increments its node's vector component. On synchronization, one version supersedes another when it is *causally later* (dominates the other clock).

Example: both nodes have an initial record `{cesena: 1}`. After disconnection:

- Cesena's edit: `{cesena: 2}`.
- Forlì's edit: `{cesena: 1, forli: 1}`.

Neither vector dominates the other, so the app keeps **both** heads and marks the report as `CONFLICT`. A user selects a candidate. A resolution at Cesena merges the vector components, then increments Cesena to obtain `{cesena: 3, forli: 1}`; this new version dominates both edits. Replication converges after synchronization.

Potential lost/found *matches*, by contrast, are different reports suggested by overlapping title keywords. They are not concurrent versions and are **not** automatically identified as a single object.

This is **manual anti-entropy**, not automatic background synchronization; if both nodes are online but nobody clicks Sync (or executes the demo), new data will not propagate. With connectivity, further synchronization and resolved conflicts, the nodes converge to the same report state.

## Tests

```bash
python -m unittest discover -s tests -v
```

- The framework-independent tests (`tests/test_core.py`) cover vector clocks, validation, persistence, HTTP/JSON exchange, two-way replication, outages, conflict detection, human resolution, idempotence and potential matching.
- Flask API tests (`tests/test_flask_optional.py`) exercise route responses if Flask is installed, and skip automatically otherwise.
- Run `python -m scripts.demo` with both servers running to verify the full user-facing HTTP scenario.

**Build verification:** 7 core tests passed in the development environment; the 2 Flask-specific tests were skipped there because this environment did not have Flask installed. Running the full app and Flask tests requires installing `requirements.txt` on a machine with package access. No unverified live Flask run is claimed.

## Files

```text
campus/core.py           SQLite, version vectors, synchronization algorithms
campus/server.py         Flask REST API and web routes
scripts/run_cesena.py    Start Cesena on localhost:5001
scripts/run_forli.py     Start Forli on localhost:5002
scripts/run_both.py      Start both independent node processes
scripts/demo.py          Repeatable outage/conflict demo (running servers needed)
templates/index.html     UI page
static/style.css         Styling
static/app.js            Browser interactions
tests/                   Automated tests
docs/                    Architecture notes, report draft and oral demo notes
requirements.txt         Python dependencies
```

## Scope and limitations

This is deliberately a small **two-node** experiment. Full version histories are exchanged on demand, so transfer cost grows with the number of edits. There's no authentication, TLS, private data handling, malicious-node protection, distributed transaction, automatic background retries or high-availability deployment. Keyword matching is illustrative, not a reliable identity-matching algorithm. A lost or found report can be marked resolved, but no identity verification or real-world handover workflow exists. These limits should be discussed in the final report and oral examination.

For a fuller architecture discussion, see `docs/ARCHITECTURE.md`; for a report draft, see `docs/FINAL_REPORT_DRAFT.md` or its PDF version.
