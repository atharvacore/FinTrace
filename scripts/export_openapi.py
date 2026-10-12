"""Write the API's OpenAPI schema to frontend/openapi.json (used to generate TypeScript types).

python scripts/export_openapi.py
"""

import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Importing the app needs a JWT secret; this one is thrown away when the script exits.
os.environ.setdefault("FINTRACE_JWT_SECRET", secrets.token_urlsafe(48))

from app.main import create_app  # noqa: E402

out = ROOT / "frontend" / "openapi.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")
print(f"Wrote {out}")
