"""Framework-independent storage and synchronization logic for the coursework prototype.

Each report is represented by immutable, versioned snapshots. Vector clocks record
causal history, so an ordinary last-writer-wins timestamp cannot silently erase
concurrent edits created while two campuses are disconnected.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import sqlite3
from threading import RLock
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

CATEGORIES = ("electronics", "keys", "documents", "clothing", "bags", "other")
KINDS = ("LOST", "FOUND")
STATUSES = ("OPEN", "RESOLVED")
EDITABLE = frozenset({"title", "description", "category", "status"})
STOPWORDS = frozenset({"lost", "found", "item", "near", "from", "with", "the", "and", "for", "a", "an", "in", "at", "my", "some", "one"})


class ProjectError(Exception):
    """A user-facing validation or state error with an HTTP-friendly status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def increment(clock: dict[str, int], node_id: str) -> dict[str, int]:
    result = clock.copy()
    result[node_id] = result.get(node_id, 0) + 1
    return result


def merge_clocks(clocks: list[dict[str, int]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for clock in clocks:
        for node, counter in clock.items():
            merged[node] = max(merged.get(node, 0), counter)
    return merged


def dominates(a: dict[str, int], b: dict[str, int]) -> bool:
    """True iff a >= b component-wise and strictly greater in >=1 component."""
    keys = set(a) | set(b)
    return all(a.get(k, 0) >= b.get(k, 0) for k in keys) and any(
        a.get(k, 0) > b.get(k, 0) for k in keys
    )


def heads_of(versions: list[dict]) -> list[dict]:
    """Only maximal, non-superseded versions; equal clocks are deduplicated."""
    winners = []
    for v in versions:
        if any(dominates(other["clock"], v["clock"]) for other in versions):
            continue
        if not any(other["clock"] == v["clock"] for other in winners):
            winners.append(v)
    return sorted(winners, key=lambda item: item["version_id"])


def cleaned_text(value: object, field: str, max_len: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ProjectError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ProjectError(f"{field} cannot be blank")
    if len(value) > max_len:
        raise ProjectError(f"{field} must be at most {max_len} characters")
    return value


def validate_report_data(data: dict) -> None:
    if not isinstance(data, dict):
        raise ProjectError("Report data must be an object")
    for key in ("id", "created_at", "updated_at", "campus"):
        cleaned_text(data.get(key), key, 100, required=True)
    cleaned_text(data.get("title"), "title", 120, required=True)
    cleaned_text(data.get("description"), "description", 1000)
    if data.get("kind") not in KINDS:
        raise ProjectError("kind must be LOST or FOUND")
    if data.get("status") not in STATUSES:
        raise ProjectError("status must be OPEN or RESOLVED")
    if data.get("category") not in CATEGORIES:
        raise ProjectError("Invalid category")


def validate_version(record: dict) -> None:
    if not isinstance(record, dict):
        raise ProjectError("Each replicated version must be an object")
    if not isinstance(record.get("version_id"), str) or not record["version_id"] or len(record["version_id"]) > 100:
        raise ProjectError("Invalid version ID")
    if not isinstance(record.get("item_id"), str) or not record["item_id"] or len(record["item_id"]) > 100:
        raise ProjectError("Invalid item ID")
    if not isinstance(record.get("origin"), str) or not record["origin"] or len(record["origin"]) > 100:
        raise ProjectError("Invalid origin")
    clock = record.get("clock")
    if not isinstance(clock, dict) or not clock or any(
        not isinstance(k, str) or not k or len(k) > 100 or type(v) is not int or v < 0
        for k, v in clock.items()
    ):
        raise ProjectError("Invalid vector clock")
    if clock.get(record["origin"], 0) < 1:
        raise ProjectError("Origin is missing from vector clock")
    validate_report_data(record.get("data"))
    if record["data"]["id"] != record["item_id"]:
        raise ProjectError("Replicated item ID mismatch")


class Store:
    def __init__(self, db_path: str, node_id: str, campus: str):
        self.db_path = str(db_path)
        self.node_id = node_id
        self.campus = campus
        self._write_lock = RLock()
        if not node_id or not campus:
            raise ValueError("Node ID and campus name are required")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    clock TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_versions_item ON versions(item_id);
                CREATE TABLE IF NOT EXISTS settings (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
            """)
            conn.execute("INSERT OR IGNORE INTO settings(name,value) VALUES ('connected','true')")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                yield conn
        finally:
            conn.close()

    def _add(self, record: dict) -> None:
        validate_version(record)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO versions(version_id,item_id,origin,clock,data) VALUES (?,?,?,?,?)",
                (record["version_id"], record["item_id"], record["origin"],
                 json.dumps(record["clock"], sort_keys=True), json.dumps(record["data"], sort_keys=True)),
            )

    def export_versions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM versions ORDER BY item_id, version_id").fetchall()
        return [{"version_id": r["version_id"], "item_id": r["item_id"],
                 "origin": r["origin"], "clock": json.loads(r["clock"]),
                 "data": json.loads(r["data"])} for r in rows]

    def import_versions(self, versions: list[dict]) -> int:
        if not isinstance(versions, list) or len(versions) > 10000:
            raise ProjectError("versions must be an array (maximum 10000)")
        for record in versions:
            validate_version(record)
        inserted = 0
        with self._connect() as conn:
            for v in versions:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO versions(version_id,item_id,origin,clock,data) VALUES (?,?,?,?,?)",
                    (v["version_id"], v["item_id"], v["origin"],
                     json.dumps(v["clock"], sort_keys=True), json.dumps(v["data"], sort_keys=True)),
                )
                inserted += cursor.rowcount
        return inserted

    def version_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]

    def _versions_for(self, item_id: str) -> list[dict]:
        return [v for v in self.export_versions() if v["item_id"] == item_id]

    def _view(self, item_id: str, versions: list[dict]) -> dict:
        heads = heads_of(versions)
        # With a conflict, do not pretend one candidate is the correct record.
        if len(heads) == 1:
            return {**deepcopy(heads[0]["data"]), "conflict": False,
                    "vector_clock": heads[0]["clock"], "head_version": heads[0]["version_id"]}
        return {"id": item_id, "conflict": True, "status": "CONFLICT",
                "candidates": [{"version_id": h["version_id"], "data": h["data"],
                                "vector_clock": h["clock"]} for h in heads]}

    def reports(self) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for record in self.export_versions():
            grouped[record["item_id"]].append(record)
        reports = [self._view(item_id, versions) for item_id, versions in grouped.items()]
        return sorted(reports, key=lambda r: r["id"])

    def report(self, item_id: str) -> dict:
        versions = self._versions_for(item_id)
        if not versions:
            raise ProjectError("Report not found", 404)
        return self._view(item_id, versions)

    def create(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ProjectError("Request body must be a JSON object")
        now = utc_now()
        data = {
            "id": str(uuid4()),
            "kind": payload.get("kind"),
            "title": payload.get("title"),
            "description": payload.get("description", ""),
            "category": payload.get("category", "other"),
            "campus": self.campus,
            "status": "OPEN",
            "created_at": now,
            "updated_at": now,
        }
        validate_report_data(data)
        self._add({"version_id": str(uuid4()), "item_id": data["id"],
                   "origin": self.node_id, "clock": {self.node_id: 1}, "data": data})
        return self.report(data["id"])

    def edit(self, item_id: str, patch: dict) -> dict:
        with self._write_lock:
            if not isinstance(patch, dict) or not patch:
                raise ProjectError("Provide at least one field to change")
            if set(patch) - EDITABLE:
                raise ProjectError("Only title, description, category and status can be edited")
            heads = heads_of(self._versions_for(item_id))
            if not heads:
                raise ProjectError("Report not found", 404)
            if len(heads) > 1:
                raise ProjectError("Resolve the conflict before editing", 409)
            data = deepcopy(heads[0]["data"])
            data.update(patch)
            data["updated_at"] = utc_now()
            validate_report_data(data)
            self._add({"version_id": str(uuid4()), "item_id": item_id,
                       "origin": self.node_id, "clock": increment(heads[0]["clock"], self.node_id),
                       "data": data})
            return self.report(item_id)

    def resolve(self, item_id: str, winning_version_id: str) -> dict:
        with self._write_lock:
            heads = heads_of(self._versions_for(item_id))
            if not heads:
                raise ProjectError("Report not found", 404)
            if len(heads) < 2:
                raise ProjectError("There is no unresolved conflict", 409)
            winner = next((v for v in heads if v["version_id"] == winning_version_id), None)
            if winner is None:
                raise ProjectError("Choose a current conflict candidate")
            merged_clock = increment(merge_clocks([h["clock"] for h in heads]), self.node_id)
            data = deepcopy(winner["data"])
            data["updated_at"] = utc_now()
            self._add({"version_id": str(uuid4()), "item_id": item_id,
                       "origin": self.node_id, "clock": merged_clock, "data": data})
            return self.report(item_id)

    def network_connected(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE name='connected'").fetchone()
        return row["value"] == "true"

    def set_network(self, connected: bool) -> bool:
        if type(connected) is not bool:
            raise ProjectError("connected must be a boolean")
        with self._connect() as conn:
            conn.execute("UPDATE settings SET value=? WHERE name='connected'",
                         ("true" if connected else "false",))
        return connected

    def sync(self, peer_url: str) -> dict:
        if not self.network_connected():
            raise ProjectError("Network partition is simulated: synchronization disabled", 503)
        if not peer_url:
            raise ProjectError("PEER_URL is not configured", 503)
        before = self.version_count()
        payload = json.dumps({"versions": self.export_versions()}).encode("utf-8")
        request = Request(peer_url.rstrip("/") + "/api/replicate", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=4) as response:
                returned = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProjectError(f"Peer unavailable or rejected synchronization: {exc}", 503) from exc
        received = self.import_versions(returned.get("versions"))
        return {"ok": True, "node": self.node_id, "peer": peer_url,
                "new_local_versions": received,
                "versions_before": before, "versions_after": self.version_count(),
                "reports": len(self.reports())}

    def possible_matches(self) -> list[dict]:
        reports = [r for r in self.reports() if not r["conflict"] and r["status"] == "OPEN"]
        lost = [r for r in reports if r["kind"] == "LOST"]
        found = [r for r in reports if r["kind"] == "FOUND"]
        matches = []
        for a in lost:
            a_words = set(re.findall(r"\w+", a["title"].lower())) - STOPWORDS
            for b in found:
                b_words = set(re.findall(r"\w+", b["title"].lower())) - STOPWORDS
                common = sorted(a_words & b_words)
                category_compatible = a["category"] == b["category"] or "other" in (a["category"], b["category"])
                if common and category_compatible:
                    matches.append({"lost": a, "found": b, "shared_keywords": common,
                                    "note": "Potential match only; requires human confirmation"})
        return matches
