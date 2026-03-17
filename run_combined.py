"""
Combined entry point: FastAPI (API at /api/*) + Dash (web app at /*).
Run with: uvicorn run_combined:app --host 0.0.0.0 --port $PORT
"""
import os
import sys

# API uses DB_URL; Heroku provides DATABASE_URL
os.environ.setdefault("DB_URL", os.environ.get("DATABASE_URL", ""))

# Add peekorobo-api to path so its imports resolve
_api_dir = os.path.join(os.path.dirname(__file__), "peekorobo-api")
sys.path.insert(0, _api_dir)

from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

# Import API app (from peekorobo-api/main.py)
import main as api_main

# Import Dash app (peekorobo.py in project root)
# When run from project root, peekorobo is the module
import peekorobo
dash_app = peekorobo.app

app = FastAPI(docs_url=None, redoc_url=None)

# Mount API at /api first (more specific paths take precedence)
app.mount("/api", api_main.app)

# Mount Dash/Flask web app at /
app.mount("/", WSGIMiddleware(dash_app.server))
