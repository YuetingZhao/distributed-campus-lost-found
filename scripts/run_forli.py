"""Start the Forlì node in terminal 2, from the repository root."""
import os
from campus.server import main

os.environ.setdefault("NODE_ID", "forli")
os.environ.setdefault("CAMPUS", "Forli")
os.environ.setdefault("DB_PATH", "data/forli.sqlite3")
os.environ.setdefault("PORT", "5002")
os.environ.setdefault("PEER_URL", "http://127.0.0.1:5001")

if __name__ == "__main__":
    main()
