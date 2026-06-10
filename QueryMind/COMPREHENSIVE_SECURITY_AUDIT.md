# Comprehensive Security Audit Report

**Date:** June 10, 2026  
**Application:** QueryMind (Text-to-SQL + RAG System)  
**Audit Scope:** Complete security verification before moving to next feature

---

## Executive Summary

This comprehensive security audit examines all critical security aspects of the QueryMind application. The audit found **3 HIGH severity issues** and **2 MEDIUM severity issues** that need immediate attention, along with several best practice recommendations.

### Overall Security Rating: 7.0/10
*(Improved from 8.5/10 after discovering new issues)*

---

## 🔴 CRITICAL ISSUES (HIGH SEVERITY)

### 1. SQL Injection Vulnerability in Table Creation
**Location:** `backend/file_handler/sql.py` (Lines 100-101)  
**Severity:** HIGH  
**Status:** ❌ VULNERABLE

**Issue:**
```python
cur.execute(f"DROP TABLE IF EXISTS {table_name}")
cur.execute(f"CREATE TABLE {table_name} ({col_defs})")
```

The code uses f-strings to construct SQL queries with the `table_name` variable directly interpolated. While `table_name` is sanitized via `_sanitize_table_name()`, the column definitions (`col_defs`) are constructed from DataFrame column names which could contain malicious content.

**Attack Vector:**
If a user uploads a CSV with malicious column names like:
```
"id); DROP TABLE users; --"
```

**Impact:**
- Arbitrary SQL execution
- Data deletion
- Database corruption
- Potential system compromise

**Recommendation:**
✅ **FIXED APPROACH:** Use parameterized queries or SQLite's table/column identifier quoting:
```python
# Safe approach using quoted identifiers
cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

# For column names, ensure quoting:
col_defs = ", ".join([
    f'"{col}" {self._map_dtype_to_sqlite(str(df[col].dtype))}'
    for col in df.columns
])
```

**Note:** The `table_name` itself is already sanitized via regex, but column names are not. Both should use quoted identifiers for defense in depth.

---

### 2. Insecure Cookie Configuration in Production
**Location:** `backend/routes/auth_endpoints.py` (Line 73)  
**Severity:** HIGH  
**Status:** ⚠️ PARTIAL - Needs Production Fix

**Issue:**
```python
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,
    secure=False,  # ❌ Should be True in production
    samesite="lax",
    max_age=86400
)
```

The `secure=False` flag means the session cookie will be transmitted over unencrypted HTTP connections.

**Attack Vector:**
- Man-in-the-middle attacks on HTTP connections
- Session hijacking via network sniffing
- Cookie theft on public WiFi

**Impact:**
- Account takeover
- Unauthorized data access
- Identity theft

**Recommendation:**
```python
import os

# Use environment variable to set based on deployment
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"

response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,
    secure=IS_PRODUCTION,  # True in production, False in development
    samesite="strict",  # Changed from "lax" to "strict" for better security
    max_age=86400
)
```

Add to `.env`:
```
ENVIRONMENT=production  # or "development"
```

---

### 3. No Session Expiry or Cleanup Mechanism
**Location:** `backend/services/session_manager.py`  
**Severity:** HIGH  
**Status:** ❌ MISSING

**Issue:**
Sessions are created and stored indefinitely with no automatic expiry or cleanup mechanism. The `last_accessed` field is tracked but never used to clean up stale sessions.

**Attack Vector:**
- Old sessions remain valid forever
- Accumulation of orphaned session data
- Increased attack surface (more sessions to target)
- Disk space exhaustion from abandoned sessions

**Impact:**
- Compromised old sessions can be reused indefinitely
- Resource exhaustion
- Privacy violations (data retained longer than necessary)

**Recommendation:**
Implement session expiry and cleanup:

```python
# Add to session_manager.py

def cleanup_expired_sessions(self, max_age_days: int = 30):
    """Delete sessions older than max_age_days."""
    from datetime import datetime, timedelta
    
    cutoff_date = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    
    with self._get_conn() as conn:
        # Find expired sessions
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE last_accessed < ?",
            (cutoff_date,)
        ).fetchall()
        
        # Delete each session and its files
        for (session_id,) in rows:
            try:
                self.delete_session(session_id)
                logger.info(f"Cleaned up expired session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_id}: {e}")

def invalidate_session(self, session_id: str):
    """Immediately invalidate a session (e.g., on logout)."""
    # Currently logout only deletes the cookie, not the session data
    # This should delete the actual session
    self.delete_session(session_id)
```

Add scheduled cleanup in `main.py`:
```python
from apscheduler.schedulers.background import BackgroundScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start session cleanup scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: session_manager.cleanup_expired_sessions(max_age_days=30),
        'interval',
        days=1  # Run daily
    )
    scheduler.start()
    
    yield
    
    scheduler.shutdown()

app = FastAPI(title="Text-2-SQL API", lifespan=lifespan)
```

---

## 🟡 MEDIUM SEVERITY ISSUES

### 4. Overly Permissive CORS Configuration
**Location:** `backend/main.py` (Lines 31-37)  
**Severity:** MEDIUM  
**Status:** ⚠️ NEEDS REVIEW

**Issue:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],  # ⚠️ Allows all HTTP methods
    allow_headers=["*"],  # ⚠️ Allows all headers
)
```

While `allow_origins` is properly restricted, `allow_methods=["*"]` and `allow_headers=["*"]` are overly permissive.

**Impact:**
- Increased attack surface
- Potential for CORS bypass techniques
- Allows unexpected HTTP methods (TRACE, PATCH, etc.)

**Recommendation:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        # Add production domain: "https://querymind.example.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Only what's needed
    allow_headers=["Content-Type", "Authorization"],  # Specific headers
    max_age=600,  # Cache preflight for 10 minutes
)
```

---

### 5. Weak Password Requirements
**Location:** `backend/routes/auth_endpoints.py` (Lines 27-28)  
**Severity:** MEDIUM  
**Status:** ⚠️ WEAK

**Issue:**
```python
if len(req.password) < 6:
    raise HTTPException(400, "Password must be at least 6 characters")
```

Only checks length, no complexity requirements.

**Attack Vector:**
- Weak passwords like "123456" or "aaaaaa" are accepted
- Susceptible to brute force and dictionary attacks

**Impact:**
- Easier account compromise
- Reduced security posture

**Recommendation:**
```python
import re

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

# In register endpoint:
is_valid, message = validate_password(req.password)
if not is_valid:
    raise HTTPException(400, message)
```

---

## ✅ SECURE AREAS (GOOD PRACTICES)

### 1. Authentication System ✓
- Centralized auth logic in `dependencies/auth.py`
- Proper password hashing with bcrypt
- HttpOnly cookies for session management
- Session ownership verification on all endpoints

### 2. Authorization Checks ✓
- All sensitive endpoints require authentication
- Session ownership verified before data access
- User-scoped data retrieval (no cross-user data leaks)

### 3. Input Sanitization ✓
- Table names sanitized with regex in `_sanitize_table_name()`
- File type validation in upload endpoints
- Content type checking for uploaded files

### 4. SQL Query Execution ✓
- User queries are executed directly (by design for text-to-SQL)
- Read-only operations (SELECT queries)
- Isolated SQLite databases per session

### 5. File Upload Security ✓
- File type restrictions (only CSV and PDF)
- Session-isolated storage
- No arbitrary file path access
- File size implicitly limited by FastAPI's UploadFile

---

## 📊 SECURITY CHECKLIST

| Category | Status | Notes |
|----------|--------|-------|
| **Authentication** | ✅ SECURE | Centralized, bcrypt hashing, HttpOnly cookies |
| **Authorization** | ✅ SECURE | Session ownership verified on all endpoints |
| **SQL Injection** | ❌ VULNERABLE | Table/column creation uses f-strings |
| **XSS Prevention** | ✅ SECURE | React escapes by default, no dangerouslySetInnerHTML |
| **CSRF Protection** | ⚠️ PARTIAL | SameSite cookies provide some protection |
| **Session Management** | ❌ VULNERABLE | No expiry, no cleanup, no invalidation on logout |
| **Cookie Security** | ⚠️ PARTIAL | secure=False in production |
| **CORS Configuration** | ⚠️ PERMISSIVE | allow_methods and allow_headers too broad |
| **Password Policy** | ⚠️ WEAK | Only length check, no complexity |
| **Rate Limiting** | ❌ MISSING | No rate limiting on any endpoint |
| **Input Validation** | ✅ SECURE | File types validated, table names sanitized |
| **Path Traversal** | ✅ SECURE | No arbitrary file paths, session-isolated storage |
| **Secret Management** | ✅ SECURE | Environment variables used via .env |
| **Logging Security** | ✅ SECURE | No sensitive data logged |

---

## 🔒 ADDITIONAL RECOMMENDATIONS

### 1. Rate Limiting (Optional but Recommended)
Add rate limiting to prevent brute force attacks:

```python
# Install: pip install slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(request: Request, response: Response, req: LoginRequest):
    # ... existing code
```

### 2. CSRF Protection
While SameSite cookies provide some protection, consider adding explicit CSRF tokens for state-changing operations:

```python
# Install: pip install fastapi-csrf-protect
from fastapi_csrf_protect import CsrfProtect

@app.post("/upload")
async def upload_file(csrf_protect: CsrfProtect = Depends(), ...):
    await csrf_protect.validate_csrf(request)
    # ... existing code
```

### 3. Security Headers
Add security headers in middleware:

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Add security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### 4. Audit Logging
Log security-sensitive operations:

```python
# Add to session_manager.py
def log_security_event(self, event_type: str, user_id: int, details: dict):
    """Log security-sensitive events."""
    logger.warning(f"SECURITY: {event_type} - user_id={user_id} - {details}")
```

Log events like:
- Failed login attempts
- Session creation/deletion
- Unauthorized access attempts
- File uploads

---

## 🎯 PRIORITY ACTION ITEMS

### Immediate (Before Next Feature)
1. ❌ **FIX SQL Injection** in `file_handler/sql.py` (Lines 100-101, quote identifiers)
2. ❌ **Implement Session Expiry** and cleanup mechanism
3. ⚠️ **Update Cookie Security** for production (secure flag based on environment)

### High Priority
4. ⚠️ **Strengthen Password Policy** (8+ chars, complexity requirements)
5. ⚠️ **Restrict CORS Configuration** (specific methods and headers)

### Medium Priority
6. 🔒 **Add Rate Limiting** on auth endpoints
7. 🔒 **Implement Session Invalidation** on logout (delete session data, not just cookie)

### Optional (Best Practices)
8. 🔒 Add CSRF protection
9. 🔒 Add security headers middleware
10. 🔒 Implement audit logging for security events

---

## 📝 NOTES

### What Was Already Secure (From Previous Audits)
- Authentication system refactored and centralized
- Session ownership verification on all endpoints
- Critical `/agent/query` endpoint secured
- No cross-user data access vulnerabilities

### New Issues Found in This Audit
- SQL injection in table creation (column names)
- No session expiry or cleanup
- Insecure cookie flag for production
- Weak password requirements
- Overly permissive CORS

### Testing Performed
- ✅ Manual code review of all security-critical files
- ✅ Authentication flow verification
- ✅ Authorization check verification
- ✅ Input validation review
- ✅ SQL injection vector analysis
- ✅ Cookie security analysis
- ✅ CORS configuration review

---

## 📚 REFERENCES

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [CWE-89: SQL Injection](https://cwe.mitre.org/data/definitions/89.html)
- [CWE-613: Insufficient Session Expiration](https://cwe.mitre.org/data/definitions/613.html)

---

**Audit Completed By:** Kiro AI Security Review  
**Next Review Date:** After implementing priority fixes
