"""
Combined entry point: FastAPI (API at /api/*) + Dash (web app at /*).
Run with: uvicorn run_combined:app --host 0.0.0.0 --port $PORT
"""
import os
import sys
import traceback
import importlib.util

def _log(msg: str) -> None:
    print(f"[run_combined] {msg}", flush=True)

# API uses DB_URL; Heroku provides DATABASE_URL
_db_url = os.environ.get("DATABASE_URL", "")
os.environ.setdefault("DB_URL", _db_url)
_log(f"DB_URL set: {bool(_db_url)}")

# Load API from peekorobo-api/main.py by path (avoids sys.path / "main" conflicts)
_api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "peekorobo-api")
_api_main_path = os.path.join(_api_dir, "main.py")
_log(f"API path: {_api_main_path}, exists: {os.path.exists(_api_main_path)}")

# Add peekorobo-api to path so its sub-imports (query.*, data.*) resolve
sys.path.insert(0, _api_dir)

try:
    from fastapi import FastAPI
    from fastapi.middleware.wsgi import WSGIMiddleware
    _log("FastAPI imports OK")
except Exception as e:
    _log(f"FastAPI import FAILED: {e}")
    traceback.print_exc()
    raise

try:
    spec = importlib.util.spec_from_file_location("peekorobo_api_main", _api_main_path)
    api_main = importlib.util.module_from_spec(spec)
    sys.modules["peekorobo_api_main"] = api_main
    spec.loader.exec_module(api_main)
    _log("API app import OK")
except Exception as e:
    _log(f"API import FAILED: {e}")
    traceback.print_exc()
    raise

try:
    import peekorobo
    dash_app = peekorobo.app
    _log("Peekorobo import OK")
except Exception as e:
    _log(f"Peekorobo import FAILED: {e}")
    traceback.print_exc()
    raise

app = FastAPI(docs_url=None, redoc_url=None)


@app.on_event("startup")
def startup():
    _log("Uvicorn startup complete - app is serving")


# Mount API at /api first (more specific paths take precedence)
app.mount("/api", api_main.app)

# Mount Dash/Flask web app at /
app.mount("/", WSGIMiddleware(dash_app.server))

_log("Combined app ready")
