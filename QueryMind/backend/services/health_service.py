# services/health_service.py
import sqlite3
from pathlib import Path

def _get_gemini_client():
    """Lazy import to avoid import errors during testing"""
    try:
        from google import genai
        from load_keys import load_config
        config = load_config()
        return genai.Client(api_key=config.get("api_key")), config
    except ImportError:
        return None, None

def check_database_health():
    """Check if session database is accessible and has correct schema"""
    try:
        db_path = "./sessions/sessions.db"
        
        # Check if sessions directory exists
        if not Path("./sessions").exists():
            return {
                "status": "error",
                "message": "Sessions directory does not exist"
            }
        
        # Try to connect
        conn = sqlite3.connect(db_path)
        
        # Check if required tables exist
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        
        required_tables = ['sessions', 'token_usage', 'conversations']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            conn.close()
            return {
                "status": "error",
                "message": f"Missing tables: {', '.join(missing_tables)}"
            }
        
        # Check sessions table schema
        cols = [c[1] for c in conn.execute('PRAGMA table_info(sessions)').fetchall()]
        required_cols = ['session_id', 'db_path', 'schema', 'chroma_path', 'created_at', 'last_accessed']
        missing_cols = [c for c in required_cols if c not in cols]
        
        if missing_cols:
            conn.close()
            return {
                "status": "warning",
                "message": f"Missing columns in sessions table: {', '.join(missing_cols)}"
            }
        
        # Count active sessions
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        
        conn.close()
        
        return {
            "status": "healthy",
            "message": "Database is accessible and schema is correct",
            "details": {
                "path": db_path,
                "tables": tables,
                "active_sessions": session_count
            }
        }
        
    except sqlite3.Error as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }


def check_gemini_health():
    """Check if Gemini API is accessible and configured correctly"""
    try:
        client, config = _get_gemini_client()
        
        if client is None:
            return {
                "status": "error",
                "message": "Failed to import Gemini dependencies"
            }
        
        api_key = config.get("api_key")
        
        # Check if API key exists
        if not api_key:
            return {
                "status": "error",
                "message": "GOOGLE_API_KEY not found in environment variables"
            }
        
        # Check if API key format is valid (basic check)
        if len(api_key) < 20:
            return {
                "status": "error",
                "message": "GOOGLE_API_KEY appears to be invalid (too short)"
            }
        
        # Try a simple API call to verify connectivity
        try:
            response = client.models.generate_content(
                model=config.get("model_name", "gemini-flash-latest"),
                contents="Say 'OK' if you can read this.",
                config={
                    "max_output_tokens": 10,
                    "temperature": 0.1
                }
            )
            response_text = response.text.strip()
            
            return {
                "status": "healthy",
                "message": "Gemini API is accessible and responding",
                "details": {
                    "model": config.get("model_name", "gemini-flash-latest"),
                    "api_key_prefix": api_key[:8] + "...",
                    "test_response": response_text[:50]
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Gemini API call failed: {str(e)}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }


def check_environment():
    """Check if all required environment variables and directories exist"""
    try:
        issues = []
        
        # Check .env file
        if not Path(".env").exists():
            issues.append(".env file not found")
        
        # Check sessions directory
        if not Path("./sessions").exists():
            issues.append("./sessions directory not found")
        
        # Check required env vars
        try:
            from load_keys import load_config
            config = load_config()
            if not config.get("api_key"):
                issues.append("GOOGLE_API_KEY not set")
        except Exception:
            issues.append("Failed to load configuration")
        
        if issues:
            return {
                "status": "warning",
                "message": "Environment issues detected",
                "details": {"issues": issues}
            }
        
        return {
            "status": "healthy",
            "message": "Environment is properly configured"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Environment check failed: {str(e)}"
        }


async def get_full_health_status():
    """Get comprehensive health status of all components"""
    db_health = check_database_health()
    gemini_health = check_gemini_health()
    env_health = check_environment()
    
    # Determine overall status
    statuses = [db_health["status"], gemini_health["status"], env_health["status"]]
    
    if "error" in statuses:
        overall_status = "unhealthy"
    elif "warning" in statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "timestamp": None,  # Will be set by the endpoint
        "components": {
            "database": db_health,
            "gemini_api": gemini_health,
            "environment": env_health
        }
    }
