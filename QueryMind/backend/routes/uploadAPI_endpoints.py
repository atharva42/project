# routes/upload.py
import io
import os
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
# Use absolute imports to reference the file handler package within the backend module.
from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
from services.session_manager import session_manager

router = APIRouter()
os.makedirs("./sessions", exist_ok=True)


def check_upload_auth(request: Request):
    """Check if user is authenticated for uploads."""
    # Get the auth session cookie
    auth_session_id = request.cookies.get("session_id")
    
    if not auth_session_id:
        return {"authenticated": False, "user": None}
    
    try:
        # This is the AUTH session, not a data session
        auth_session = session_manager.get_session(auth_session_id)
        if not auth_session.get('user_id'):
            return {"authenticated": False, "user": None}
        
        user = session_manager.get_user_by_id(auth_session['user_id'])
        return {
            "authenticated": True,
            "user": {"id": user['id'], "username": user['username']}
        }
    except Exception:
        return {"authenticated": False, "user": None}


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), session_id: str = None):
    """
    Unified upload endpoint that routes to appropriate handler based on file type.
    
    If session_id is provided, appends to existing session (Option 1: multi-file sessions).
    If session_id is None, creates a new session.
    """
    # Check authentication
    auth_status = check_upload_auth(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # If session_id provided, verify it belongs to this user
    if session_id:
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
                raise HTTPException(403, "Access denied: Session belongs to another user")
        except ValueError:
            raise HTTPException(404, "Session not found")
    
    filename = file.filename or ""
    content_type = file.content_type or ""
    
    print(f"[UPLOAD] Received file: {filename}, content_type: {content_type}")
    
    # Detect file type by extension
    if filename.lower().endswith(".csv"):
        # Pass auth_status to avoid double-checking
        return await upload_csv_internal(request, file, session_id, auth_status)
    
    elif filename.lower().endswith(".pdf"):
        # Pass auth_status to avoid double-checking
        return await upload_pdf_internal(request, file, session_id, auth_status)
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {filename}. Supported types: .csv, .pdf"
        )


async def upload_csv_internal(request: Request, file: UploadFile, session_id: str, auth_status: dict):
    """Internal CSV upload handler that receives auth_status."""
    user_id = auth_status["user"]["id"]
    
    print(f"[UPLOAD] Processing CSV: {file.filename}")

    content = await file.read()
    file_like = io.BytesIO(content)
    file_like.name = file.filename

    # Check if session_id provided (append mode) or create new session
    if session_id:
        # Validate session exists and belongs to this user
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") and session.get("user_id") != user_id:
                raise HTTPException(403, "Access denied: Session belongs to another user")
            print(f"[UPLOAD] Appending to existing session: {session_id}")
        except ValueError:
            raise HTTPException(400, f"Session {session_id} not found")
        
        # Reuse existing db_path
        sql_handler = SQL([file_like], session_id)
        schema = sql_handler.fetch_schema()
        
        # Update session with new schema (merge with existing)
        existing_schema = session.get("schema") or {}
        if not isinstance(existing_schema, dict):
            existing_schema = {}
        existing_schema.update(schema)

        session_manager.update_session(session_id, {
            "db_path": sql_handler.db_path,
            "schema": existing_schema
        })
        
        return {
            "session_id": session_id,
            "file_type": "csv",
            "message": "CSV appended to existing session",
            "tables": list(schema.keys()),
            "schema": schema
        }
    else:
        # Create new session linked to this user
        session_id = session_manager.create_session(user_id=user_id)
        print(f"[UPLOAD] Created new session: {session_id}")

        sql_handler = SQL([file_like], session_id)
        schema = sql_handler.fetch_schema()

        print(f"[UPLOAD] File '{file.filename}' loaded successfully into session '{session_id}'")

        for table_name in schema.keys():
            rows, cols = sql_handler.sql_query(f"SELECT * FROM {table_name} LIMIT 10")
            df = pd.DataFrame(rows, columns=cols)
            print(f"[SCHEMA PREVIEW] Table: {table_name}")
            print(df.to_string(index=False))
            print("-" * 60)

        session_manager.update_session(session_id, {
            "db_path": sql_handler.db_path,
            "schema": schema
        })

        return {
            "session_id": session_id,
            "file_type": "csv",
            "tables": list(schema.keys()),
            "schema": schema
        }


@router.post("/upload/csv")
async def upload_csv(request: Request, file: UploadFile = File(...), session_id: str = None):
    """Public CSV upload endpoint - checks auth and delegates to internal handler."""
    auth_status = check_upload_auth(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session ownership if provided
    if session_id:
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
                raise HTTPException(403, "Access denied: Session belongs to another user")
        except ValueError:
            raise HTTPException(404, "Session not found")
    
    return await upload_csv_internal(request, file, session_id, auth_status)


async def upload_pdf_internal(request: Request, file: UploadFile, session_id: str, auth_status: dict):
    """Internal PDF upload handler that receives auth_status."""
    user_id = auth_status["user"]["id"]
    
    print(f"[UPLOAD] Processing PDF: {file.filename}")
    
    # Check if session_id provided (append mode) or create new session
    session = None
    if session_id:
        # Validate session exists and belongs to this user
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") and session.get("user_id") != user_id:
                raise HTTPException(403, "Access denied: Session belongs to another user")
            print(f"[UPLOAD] Appending PDF to existing session: {session_id}")
        except ValueError:
            raise HTTPException(400, f"Session {session_id} not found")
    else:
        session_id = session_manager.create_session(user_id=user_id)
        session = session_manager.get_session(session_id)
        print(f"[UPLOAD] Created session: {session_id}")
    
    try:
        # Build or get the current PDF file list
        pdf_files = session.get("pdf_files") or []
        if not isinstance(pdf_files, list):
            pdf_files = []
        
        # Check if file already exists in this session
        if file.filename in pdf_files:
            print(f"[UPLOAD] PDF '{file.filename}' already exists in session {session_id}. Skipping re-processing.")
            return {
                "session_id": session_id,
                "file_type": "pdf",
                "message": f"PDF '{file.filename}' already uploaded to this session. Skipped re-processing.",
                "chunks": 0,
                "files": pdf_files,
                "already_exists": True
            }
        
        # Read PDF content
        content = await file.read()
        pdf_file = io.BytesIO(content)
        
        # Initialize PDF handler
        pdf_handler = PDFHandler(session_id)
        
        # Process and store PDF
        num_chunks = pdf_handler.add_pdf(pdf_file, file.filename)
        
        print(f"[UPLOAD] PDF '{file.filename}' processed: {num_chunks} chunks stored")
        
        # Add to the PDF file list
        pdf_files.append(file.filename)

        # Update session with chroma_path and uploaded PDF filenames
        session_manager.update_session(session_id, {
            "chroma_path": pdf_handler.chroma_path,
            "pdf_files": pdf_files
        })
        
        return {
            "session_id": session_id,
            "file_type": "pdf",
            "message": f"PDF processed successfully. {num_chunks} chunks stored.",
            "chunks": num_chunks,
            "files": pdf_files
        }
    
    except Exception as e:
        print(f"[ERROR] PDF processing failed: {str(e)}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")


@router.post("/upload/pdf")
async def upload_pdf(request: Request, file: UploadFile = File(...), session_id: str = None):
    """Public PDF upload endpoint - checks auth and delegates to internal handler."""
    auth_status = check_upload_auth(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session ownership if provided
    if session_id:
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
                raise HTTPException(403, "Access denied: Session belongs to another user")
        except ValueError:
            raise HTTPException(404, "Session not found")
    
    return await upload_pdf_internal(request, file, session_id, auth_status)
