# routes/upload.py
import io
import os
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
from services.session_manager import session_manager

router = APIRouter()
os.makedirs("./sessions", exist_ok=True)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = None):
    """
    Unified upload endpoint that routes to appropriate handler based on file type.
    
    If session_id is provided, appends to existing session (Option 1: multi-file sessions).
    If session_id is None, creates a new session.
    """
    filename = file.filename or ""
    content_type = file.content_type or ""
    
    print(f"[UPLOAD] Received file: {filename}, content_type: {content_type}")
    
    # Detect file type by extension
    if filename.lower().endswith(".csv"):
        return await upload_csv(file, session_id)
    
    elif filename.lower().endswith(".pdf"):
        return await upload_pdf(file, session_id)
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {filename}. Supported types: .csv, .pdf"
        )


@router.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...), session_id: str = None):
    """Upload and process CSV file - stores in SQLite for SQL queries.
    
    If session_id is provided, appends to existing session.
    If session_id is None, creates a new session.
    """
    print(f"[UPLOAD] Processing CSV: {file.filename}")

    content = await file.read()
    file_like = io.BytesIO(content)
    file_like.name = file.filename

    # Check if session_id provided (append mode) or create new session
    if session_id:
        # Validate session exists
        try:
            session = session_manager.get_session(session_id)
            print(f"[UPLOAD] Appending to existing session: {session_id}")
        except ValueError:
            raise HTTPException(400, f"Session {session_id} not found")
        
        # Reuse existing db_path
        sql_handler = SQL([file_like], session_id)
        schema = sql_handler.fetch_schema()
        
        # Update session with new schema (merge with existing)
        existing_schema = session.get("schema", {})
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
        # Create new session
        session_id = session_manager.create_session()
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


@router.post("/upload/pdf")
async def upload_pdf(file: UploadFile = File(...), session_id: str = None):
    """
    Upload and process PDF file - stores in ChromaDB for RAG queries.
    
    If session_id is provided, appends to existing session.
    If session_id is None, creates a new session.
    """
    print(f"[UPLOAD] Processing PDF: {file.filename}")
    
    # Check if session_id provided (append mode) or create new session
    if session_id:
        # Validate session exists
        try:
            session = session_manager.get_session(session_id)
            print(f"[UPLOAD] Appending PDF to existing session: {session_id}")
        except ValueError:
            raise HTTPException(400, f"Session {session_id} not found")
    else:
        session_id = session_manager.create_session()
        print(f"[UPLOAD] Created session: {session_id}")
    
    try:
        # Read PDF content
        content = await file.read()
        pdf_file = io.BytesIO(content)
        
        # Initialize PDF handler
        pdf_handler = PDFHandler(session_id)
        
        # Process and store PDF
        num_chunks = pdf_handler.add_pdf(pdf_file, file.filename)
        
        print(f"[UPLOAD] PDF '{file.filename}' processed: {num_chunks} chunks stored")
        
        # Update session with chroma_path
        session_manager.update_session(session_id, {
            "chroma_path": pdf_handler.chroma_path
        })
        
        return {
            "session_id": session_id,
            "file_type": "pdf",
            "message": f"PDF processed successfully. {num_chunks} chunks stored.",
            "chunks": num_chunks
        }
    
    except Exception as e:
        print(f"[ERROR] PDF processing failed: {str(e)}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")
