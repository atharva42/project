# routes/upload.py
import io
import os
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from dependencies.auth import CurrentUser, AuthUser, verify_session_ownership
from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
from services.session_manager import session_manager
from services.langgraph_agent import get_user_friendly_error

router = APIRouter()
os.makedirs("./sessions", exist_ok=True)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = None, user: AuthUser = CurrentUser):
    """
    Unified upload endpoint that routes to appropriate handler based on file type.
    
    If session_id is provided, appends to existing session (Option 1: multi-file sessions).
    If session_id is None, creates a new session.
    """
    # If session_id provided, verify it belongs to this user
    if session_id:
        verify_session_ownership(session_id, user)
    
    filename = file.filename or ""
    content_type = file.content_type or ""
    
    print(f"[UPLOAD] Received file: {filename}, content_type: {content_type}")
    
    # Detect file type by extension
    if filename.lower().endswith(".csv"):
        return await upload_csv_internal(file, session_id, user)
    
    elif filename.lower().endswith(".pdf"):
        return await upload_pdf_internal(file, session_id, user)
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {filename}. Supported types: .csv, .pdf"
        )


async def upload_csv_internal(file: UploadFile, session_id: str, user: AuthUser):
    """Internal CSV upload handler."""
    print(f"[UPLOAD] Processing CSV: {file.filename}")

    content = await file.read()
    file_like = io.BytesIO(content)
    file_like.name = file.filename

    # Check if session_id provided (append mode) or create new session
    if session_id:
        # Session already verified by caller
        session = session_manager.get_session(session_id)
        print(f"[UPLOAD] Appending to existing session: {session_id}")
        
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
        session_id = session_manager.create_session(user_id=user.id)
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
async def upload_csv(file: UploadFile = File(...), session_id: str = None, user: AuthUser = CurrentUser):
    """Public CSV upload endpoint."""
    # Verify session ownership if provided
    if session_id:
        verify_session_ownership(session_id, user)
    
    return await upload_csv_internal(file, session_id, user)


async def upload_pdf_internal(file: UploadFile, session_id: str, user: AuthUser):
    """Internal PDF upload handler."""
    print(f"[UPLOAD] Processing PDF: {file.filename}")
    
    # Check if session_id provided (append mode) or create new session
    session = None
    if session_id:
        # Session already verified by caller
        session = session_manager.get_session(session_id)
        print(f"[UPLOAD] Appending PDF to existing session: {session_id}")
    else:
        session_id = session_manager.create_session(user_id=user.id)
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
        
        # Process and store PDF — returns (num_chunks, extracted_text)
        # so we can pass the text to generate_summary without re-reading the file.
        num_chunks, extracted_text = pdf_handler.add_pdf(pdf_file, file.filename)
        
        print(f"[UPLOAD] PDF '{file.filename}' processed: {num_chunks} chunks stored")

        # Generate routing summary from the already-extracted text.
        # Done at upload time so there is zero cost per query.
        summary = pdf_handler.generate_summary(extracted_text, file.filename)

        # Merge into the session's pdf_summaries dict {filename: summary}
        pdf_summaries = session.get("pdf_summaries") or {}
        if not isinstance(pdf_summaries, dict):
            pdf_summaries = {}
        pdf_summaries[file.filename] = summary
        
        # Add to the PDF file list
        pdf_files.append(file.filename)

        # Update session with chroma_path, PDF filenames, and summaries
        session_manager.update_session(session_id, {
            "chroma_path": pdf_handler.chroma_path,
            "pdf_files": pdf_files,
            "pdf_summaries": pdf_summaries
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
        raise HTTPException(500, get_user_friendly_error(str(e)))


@router.post("/upload/pdf")
async def upload_pdf(file: UploadFile = File(...), session_id: str = None, user: AuthUser = CurrentUser):
    """Public PDF upload endpoint."""
    # Verify session ownership if provided
    if session_id:
        verify_session_ownership(session_id, user)
    
    return await upload_pdf_internal(file, session_id, user)
