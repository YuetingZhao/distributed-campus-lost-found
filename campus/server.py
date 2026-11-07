"""Flask REST API + UI for one independent campus node.

Run two processes with distinct NODE_ID, PORT, DB_PATH and reciprocal PEER_URL.
All endpoints are for a local educational demonstration, NOT the public Internet.
"""
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from campus.core import ProjectError, Store


def create_app(config=None):
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
                static_folder=str(Path(__file__).resolve().parent.parent / "static"))
    app.config.update(
        NODE_ID=os.getenv("NODE_ID", "cesena"),
        CAMPUS=os.getenv("CAMPUS", "Cesena"),
        DB_PATH=os.getenv("DB_PATH", "data/cesena.sqlite3"),
        PEER_URL=os.getenv("PEER_URL", "http://127.0.0.1:5002"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)
    store = Store(app.config["DB_PATH"], app.config["NODE_ID"], app.config["CAMPUS"])
    app.extensions["campus_store"] = store

    @app.errorhandler(ProjectError)
    def user_error(exc):
        return jsonify({"error": str(exc)}), exc.status

    @app.errorhandler(413)
    def oversized(_exc):
        return jsonify({"error": "Payload too large (5 MiB maximum)"}), 413

    def json_body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ProjectError("Expected a JSON object")
        return data

    @app.get("/")
    def index():
        return render_template("index.html", node_id=store.node_id, campus=store.campus)

    @app.get("/api/health")
    def health():
        return jsonify({"node": store.node_id, "campus": store.campus,
                        "connected": store.network_connected(),
                        "peer": app.config["PEER_URL"],
                        "versions": store.version_count(), "reports": len(store.reports())})

    @app.get("/api/items")
    def get_items():
        return jsonify({"items": store.reports()})

    @app.post("/api/items")
    def create_item():
        return jsonify(store.create(json_body())), 201

    @app.get("/api/items/<item_id>")
    def get_item(item_id):
        return jsonify(store.report(item_id))

    @app.patch("/api/items/<item_id>")
    def edit_item(item_id):
        return jsonify(store.edit(item_id, json_body()))

    @app.post("/api/items/<item_id>/resolve")
    def resolve_item(item_id):
        data = json_body()
        return jsonify(store.resolve(item_id, data.get("winning_version_id")))

    @app.get("/api/matches")
    def get_matches():
        return jsonify({"matches": store.possible_matches()})

    @app.post("/api/sync")
    def sync():
        return jsonify(store.sync(app.config["PEER_URL"]))

    @app.post("/api/replicate")
    def replicate():
        if not store.network_connected():
            raise ProjectError("This node is partitioned and cannot replicate", 503)
        inserted = store.import_versions(json_body().get("versions"))
        return jsonify({"inserted": inserted, "versions": store.export_versions()})

    @app.get("/api/admin/network")
    def get_network():
        return jsonify({"connected": store.network_connected()})

    @app.put("/api/admin/network")
    def set_network():
        return jsonify({"connected": store.set_network(json_body().get("connected"))})

    return app


def main():
    app = create_app()
    port = int(os.getenv("PORT", "5001"))
    print(f"\n{app.config['CAMPUS']} node: http://127.0.0.1:{port}  (peer: {app.config['PEER_URL']})")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
