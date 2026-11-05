"""Production health check script verifying Streamlit server and SQLite integrity."""
import os
import sys
import urllib.request
from app.data.db import check_db_health

def main() -> int:
    port = os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("PORT") or "8501"
    try:
        req = urllib.request.Request(f"http://localhost:{port}/_stcore/health", headers={"User-Agent": "CP-Coach-Healthcheck"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                sys.stderr.write(f"Streamlit HTTP healthcheck returned status {resp.status}\n")
                return 1
    except Exception as e:
        sys.stderr.write(f"Streamlit server unreachable on port {port}: {e}\n")
        return 1

    db_status = check_db_health()
    if not db_status.get("healthy"):
        sys.stderr.write(f"Database healthcheck failed: {db_status.get('error', 'Integrity issue')}\n")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
