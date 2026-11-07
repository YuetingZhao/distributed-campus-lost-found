"""Run the end-to-end outage/reconciliation demo against two running Flask nodes.

From repository root: python -m scripts.demo
Uses only the standard library. Adds a few new example reports each run.
"""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

A = "http://127.0.0.1:5001"
B = "http://127.0.0.1:5002"


def request(base, path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(base + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def show(label, response):
    status, body = response
    print(f"{label} => HTTP {status}: {json.dumps(body, ensure_ascii=False)[:230]}")
    return status, body


def run():
    print("\n== Distributed Campus Lost & Found: demonstration ==")
    assert request(A, "/api/health")[0] == 200, "Start Cesena first"
    assert request(B, "/api/health")[0] == 200, "Start Forli first"
    for base in (A, B):
        request(base, "/api/admin/network", "PUT", {"connected": True})

    print("\n1. Online: create one record in Cesena and replicate it")
    _, new = show("Create", request(A, "/api/items", "POST",
        {"kind":"LOST", "title":"Black MacBook charger", "description":"Library desk", "category":"electronics"}))
    item_id = new["id"]
    show("Sync A -> B", request(A, "/api/sync", "POST"))
    assert request(B, "/api/items/" + item_id)[0] == 200

    print("\n2. Isolate both campuses; they remain locally available")
    for base in (A, B):
        show("Partition", request(base, "/api/admin/network", "PUT", {"connected":False}))
    assert request(A, "/api/sync", "POST")[0] == 503
    assert request(B, "/api/sync", "POST")[0] == 503
    show("Edit at Cesena", request(A, "/api/items/" + item_id, "PATCH", {"description":"Near first-floor desk"}))
    show("Edit at Forli", request(B, "/api/items/" + item_id, "PATCH", {"description":"Library entrance"}))
    show("Locally create FOUND record", request(B, "/api/items", "POST",
        {"kind":"FOUND", "title":"MacBook charger", "description":"Found near hall", "category":"electronics"}))

    print("\n3. Reconnect, exchange data, observe conflict")
    for base in (A, B):
        request(base, "/api/admin/network", "PUT", {"connected":True})
    show("Sync B -> A", request(B, "/api/sync", "POST"))
    _, a_conflict = request(A, "/api/items/" + item_id)
    _, b_conflict = request(B, "/api/items/" + item_id)
    assert a_conflict["conflict"] and b_conflict["conflict"]
    show("Conflict detection", (200, {"id":item_id, "candidates":a_conflict["candidates"]}))
    assert request(A, "/api/items/" + item_id, "PATCH", {"status":"RESOLVED"})[0] == 409

    print("\n4. Human selects a version; the merge dominates both histories")
    winner_id = a_conflict["candidates"][0]["version_id"]
    show("Resolve at Cesena", request(A, "/api/items/" + item_id + "/resolve", "POST",
                                     {"winning_version_id": winner_id}))
    show("Sync resolution", request(A, "/api/sync", "POST"))
    _, final_a = request(A, "/api/items/" + item_id)
    _, final_b = request(B, "/api/items/" + item_id)
    assert not final_a["conflict"] and final_a == final_b
    _, suggested = request(A, "/api/matches")
    print(f"\n5. Matched LOST/FOUND pairs (separate reports, not data conflicts): {len(suggested['matches'])}")
    print("\nPASS: create, replication, outage, independent edits, detection, resolution, convergence")


if __name__ == "__main__":
    run()
