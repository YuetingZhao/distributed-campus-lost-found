"""Start the Cesena node in terminal 1, from the repository root."""
import os
from campus.server import main

os.environ.setdefault("NODE_ID", "cesena")
os.environ.setdefault("CAMPUS", "Cesena")
os.environ.setdefault("DB_PATH", "data/cesena.sqlite3")
os.environ.setdefault("PORT", "5001")
os.environ.setdefault("PEER_URL", "http://127.0.0.1:5002")

if __name__ == "__main__":
    main()
