"""
TEMPORARY DEMO FEATURE — one preloaded multi-file session for recruiters/demos.

Lets anyone (any logged-in user) try the app without uploading. It seeds a
SINGLE shared session containing every file in ``backend/demo_files/`` — the
CSVs go into that session's SQL database and the PDFs into its ChromaDB. Having
both modalities in one session lets a recruiter exercise the router (SQL vs RAG
vs combined). The session is created with ``user_id=None`` so
``verify_session_ownership`` treats it as public (the check is skipped when
user_id is falsy).

>>> HOW TO USE
    1. Drop CSV/PDF files into ``backend/demo_files/``.
    2. Start the backend, then hit GET /demo/datasets once (the frontend does
       this automatically on load) to seed them.

>>> HOW TO REMOVE (this is not meant to ship)
    1. Delete this file (routes/demo.py).
    2. Remove the demo router include line in main.py.
    3. Remove the "Demo" blocks in frontend/src/App.jsx and the isDemoSession
       prop/guard in frontend/src/components/UploadForm.jsx.
    4. Delete the backend/demo_files/ folder and backend/demo_sessions.json.
"""
import io
import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
from services.session_manager import session_manager

router = APIRouter()

DEMO_FILES_DIR = Path("./demo_files")
DEMO_REGISTRY = Path("./demo_sessions.json")

# Guard so concurrent first-requests don't double-seed.
_seed_lock = threading.Lock()


def _load_registry() -> dict:
    """Registry is a single dict: {"session_id": str, "files": [{name, file_type}]}."""
    if DEMO_REGISTRY.exists():
        try:
            data = json.loads(DEMO_REGISTRY.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_registry(entry: dict) -> None:
    DEMO_REGISTRY.write_text(json.dumps(entry, indent=2))


def _seed_demo_session() -> dict:
    """Create ONE shared (user_id=None) session loaded with every demo file.

    Idempotent: if a valid session is already registered, returns it unchanged.
    CSVs are loaded into the session's SQLite DB; PDFs into its ChromaDB, so the
    resulting session has both modalities and routes through the agent's router.
    """
    with _seed_lock:
        registry = _load_registry()

        # Already seeded and the session still exists -> reuse.
        if registry.get("session_id"):
            try:
                session_manager.get_session(registry["session_id"])
                return registry
            except Exception:
                registry = {}  # stale (e.g. DB wiped on redeploy) -> re-seed

        if not DEMO_FILES_DIR.exists():
            return {}

        files = [p for p in sorted(DEMO_FILES_DIR.iterdir())
                 if p.is_file() and p.suffix.lower() in (".csv", ".pdf")]
        if not files:
            return {}

        session_id = session_manager.create_session(user_id=None)
        files_meta = []
        merged_schema = {}
        db_path = None
        chroma_path = None
        pdf_files = []

        for path in files:
            name = path.name
            ext = path.suffix.lower()
            try:
                if ext == ".csv":
                    file_like = io.BytesIO(path.read_bytes())
                    file_like.name = name
                    # Each call appends its table(s) to the same session DB.
                    sql_handler = SQL([file_like], session_id)
                    merged_schema.update(sql_handler.fetch_schema())
                    db_path = sql_handler.db_path
                    files_meta.append({"name": name, "file_type": "csv"})
                    print(f"[DEMO] Loaded CSV '{name}' into session {session_id}")
                elif ext == ".pdf":
                    pdf_handler = PDFHandler(session_id)
                    pdf_handler.add_pdf(io.BytesIO(path.read_bytes()), name)
                    chroma_path = pdf_handler.chroma_path
                    pdf_files.append(name)
                    files_meta.append({"name": name, "file_type": "pdf"})
                    print(f"[DEMO] Loaded PDF '{name}' into session {session_id}")
            except Exception as e:
                print(f"[DEMO] Failed to load '{name}': {e}")

        update = {}
        if db_path:
            update["db_path"] = db_path
            update["schema"] = merged_schema
        if chroma_path:
            update["chroma_path"] = chroma_path
            update["pdf_files"] = pdf_files
        session_manager.update_session(session_id, update)

        registry = {"session_id": session_id, "files": files_meta}
        _save_registry(registry)
        print(f"[DEMO] Seeded combined demo session {session_id} with {len(files_meta)} files")
        return registry


@router.get("/demo/datasets")
async def demo_datasets():
    """Return the single combined demo session (seeding it once if needed). Public.

    Shape: ``{"session_id": str, "files": [{"name", "file_type"}]}`` — or ``{}``
    if there are no demo files / the session no longer exists.
    """
    registry = _seed_demo_session()
    if not registry.get("session_id"):
        return {}
    try:
        session_manager.get_session(registry["session_id"])
    except Exception:
        return {}
    return registry


@router.get("/demo/file/{name}")
async def demo_file(name: str):
    """Serve a raw demo file for inline viewing in the browser. Public.

    Only files registered in the demo session can be served, and we reduce the
    requested name to its basename, so arbitrary path traversal is blocked.
    """
    safe = Path(name).name  # strip any directory components
    known = {f["name"] for f in _load_registry().get("files", [])}
    if safe not in known:
        raise HTTPException(404, "Demo file not found")

    path = DEMO_FILES_DIR / safe
    if not path.is_file():
        raise HTTPException(404, "Demo file not found")

    media = "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain"
    return FileResponse(
        str(path),
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="{safe}"'},
    )
