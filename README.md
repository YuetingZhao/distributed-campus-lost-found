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

## How to run the project

The project requires Python 3.10 or later.

First, open a terminal in the project folder and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start both campus servers:

```bash
python -m scripts.run_both
```

Then open the two pages in your browser:

- Cesena: http://127.0.0.1:5001
- Forlì: http://127.0.0.1:5002

Both servers run locally on the same computer. Each campus uses its own SQLite database.

To stop the servers, press `Ctrl + C` in the terminal.

## Testing the application

I tested the application locally using two nodes: Cesena and Forlì.

I first created a lost-item report in Cesena and synchronized it with Forlì.

Then I simulated a network disconnection. During the disconnection, I created a new report in Cesena and verified that it was not immediately visible in Forlì. After restoring the connection and synchronizing, both nodes had the same data.

I also tested concurrent updates to the same report. The application detected a conflict, and I selected one version to resolve it.

Finally, I tested the lost/found matching feature using reports with similar keywords.

### Run the automated demonstration

Start both nodes:

```bash
python -m scripts.run_both
```

In another terminal, run:

```bash
python -m scripts.demo
```

The demonstration checks synchronization, network disconnection, conflict detection and resolution.

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

**Local test results:** I ran the tests on macOS with Python 3.11.2 and Flask installed. All 9 tests passed successfully (0 failures, 0 skipped).
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
