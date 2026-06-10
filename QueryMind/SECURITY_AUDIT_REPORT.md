# QueryMind Authentication & Authorization Security Audit

**Date**: June 10, 2026  
**Status**: ⚠️ **CRITICAL ISSUES FOUND**

---

## 🔴 **CRITICAL SECURITY ISSUES**

### **1. UNPROTECTED ENDPOINT - `/agent/query`**
**Severity**: 🔴 CRITICAL  
**File**: `backend/routes/graph.py`  
**Issue**: The `/agent/query` endpoint has **NO authentication or authorization checks**

```python
@router.post("/agent/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    # ❌ NO AUTH CHECK HERE!
    result = run_agent(request.session_id, request.question)
    return AgentQueryResponse(...)
```

**Risk**: 
- ✅ Anyone can query ANY session without authentication
- ✅ Attackers can access other users' data by guessing session IDs
- ✅ No user isolation - complete data breach risk

**Fix Required**: Add authentication and session ownership verification

---

### **2. HEALTH CHECK ENDPOINT - Public Access**
**Severity**: 🟡 LOW (Informational)  
**File**: `backend/routes/API_endpoints.py`  
**Issue**: `/get_system_health` is publicly accessible

```python
@router.get("/get_system_health")
async def health():
    # ❌ NO AUTH CHECK - But this is okay for monitoring
    health_status = await get_full_health_status()
    return health_status
```

**Risk**: Low - Health checks are typically public for monitoring  
**Recommendation**: Consider restricting to admin users or rate-limiting

---

## ✅ **PROPERLY SECURED ENDPOINTS**

### **Authentication Endpoints** ✅
All auth endpoints work correctly:
- `POST /auth/register` - ✅ Proper validation
- `POST /auth/login` - ✅ Bcrypt password hashing
- `GET /auth/status` - ✅ Cookie-based session check
- `POST /auth/logout` - ✅ Cookie deletion

### **Protected Endpoints** ✅
The following endpoints have proper auth + authorization:

#### **Session Management**
- ✅ `POST /session` - Requires auth, links to user
- ✅ `GET /schema/{session_id}` - Auth + ownership check
- ✅ `POST /chat` - Auth + ownership check
- ✅ `GET /usage_tokens` - Auth + ownership check

#### **File Uploads**
- ✅ `POST /upload` - Auth + ownership check
- ✅ `POST /upload/csv` - Auth + ownership check
- ✅ `POST /upload/pdf` - Auth + ownership check

#### **Conversations**
- ✅ `GET /conversations` - Auth + ownership check
- ✅ `POST /conversations/save` - Auth + ownership check
- ✅ `DELETE /conversations/{conv_id}` - Auth + ownership check

---

## 🔐 **AUTHENTICATION IMPLEMENTATION ANALYSIS**

### **Backend: Cookie-Based Sessions** ✅

```python
# Login creates session cookie
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,        # ✅ Prevents XSS
    secure=False,         # ⚠️  Should be True in production
    samesite="lax",       # ✅ CSRF protection
    max_age=86400         # ✅ 24 hour expiry
)
```

**Good**:
- HttpOnly cookies prevent XSS attacks
- SameSite=lax provides CSRF protection
- 24-hour session timeout

**Needs Improvement**:
- `secure=False` - should be `True` in production (HTTPS only)

---

### **Password Security** ✅

```python
# Registration
password_hash = bcrypt.hashpw(
    req.password.encode('utf-8'), 
    bcrypt.gensalt()
).decode('utf-8')

# Login verification
is_valid = bcrypt.checkpw(
    req.password.encode('utf-8'), 
    user['password_hash'].encode('utf-8')
)
```

**Good**:
- ✅ Bcrypt hashing (industry standard)
- ✅ Salt generation per password
- ✅ Minimum 6 character requirement
- ✅ Password never stored in plaintext

---

### **Authorization Pattern** ✅

All protected endpoints follow this pattern:

```python
# Step 1: Check authentication
auth_status = check_auth_status(request)
if not auth_status["authenticated"]:
    raise HTTPException(401, "Not authenticated")

# Step 2: Get session
session = session_manager.get_session(session_id)

# Step 3: Verify ownership
if session.get("user_id") != auth_status["user"]["id"]:
    raise HTTPException(403, "Access denied: Session belongs to another user")
```

**Good**:
- ✅ Proper HTTP status codes (401 vs 403)
- ✅ User isolation enforced
- ✅ Clear error messages

---

### **Frontend Authentication** ✅

```javascript
// AuthContext provides:
- user state management
- Cookie-based authentication
- Automatic redirect to /login if not authenticated
- Axios configured with withCredentials: true
```

**Good**:
- ✅ React Context for global auth state
- ✅ Protected routes redirect to login
- ✅ Cookies automatically sent with requests
- ✅ Loading states handled

---

## 🔍 **SESSION MANAGEMENT ANALYSIS**

### **Database Schema** ✅

```sql
-- Sessions table links to users
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER,              -- ✅ Linked to user
    db_path TEXT,
    schema TEXT,
    chroma_path TEXT,
    pdf_files TEXT,
    created_at TEXT,
    last_accessed TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Good**:
- ✅ Foreign key constraint enforces referential integrity
- ✅ Sessions are linked to user_id
- ✅ Timestamps for auditing

---

### **Session Creation** ✅

```python
def create_session(self, user_id: int = None) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (..., user_id, ...) VALUES (?, ?, ...)",
        (session_id, user_id, ...)
    )
    return session_id
```

**Good**:
- ✅ UUID v4 for session IDs (hard to guess)
- ✅ User ID linked at creation
- ✅ Proper database transaction

---

## 🚨 **VULNERABILITIES SUMMARY**

| Severity | Issue | Endpoint | Impact |
|----------|-------|----------|--------|
| 🔴 CRITICAL | No authentication | `/agent/query` | Anyone can access any user's data |
| 🟡 LOW | Public health check | `/get_system_health` | Information disclosure (acceptable) |
| 🟡 LOW | Secure flag disabled | Cookie settings | Only affects production HTTPS |

---

## 🛠️ **REQUIRED FIXES**

### **Priority 1: Fix `/agent/query` Endpoint** 🔴

```python
# BEFORE (VULNERABLE):
@router.post("/agent/query")
async def agent_query(request: AgentQueryRequest):
    result = run_agent(request.session_id, request.question)
    return result

# AFTER (SECURE):
@router.post("/agent/query")
async def agent_query(request: Request, agent_request: AgentQueryRequest):
    # Check authentication
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session ownership
    try:
        session = session_manager.get_session(agent_request.session_id)
        if session.get("user_id") != auth_status["user"]["id"]:
            raise HTTPException(403, "Access denied: Session belongs to another user")
    except ValueError:
        raise HTTPException(404, "Session not found")
    
    # Now safe to execute
    result = run_agent(agent_request.session_id, agent_request.question)
    return result
```

### **Priority 2: Production Cookie Settings** 🟡

```python
# In auth_endpoints.py - login()
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,
    secure=True,        # ✅ Change to True for production
    samesite="strict",  # ✅ Consider stricter policy
    max_age=86400
)
```

---

## ✅ **SECURITY STRENGTHS**

1. **Strong Authentication**
   - Bcrypt password hashing
   - HttpOnly cookies
   - SameSite CSRF protection

2. **Proper Authorization**
   - User isolation enforced
   - Session ownership verification
   - Foreign key constraints

3. **Secure Code Patterns**
   - Proper HTTP status codes
   - Clear error messages
   - Transaction safety

4. **Frontend Security**
   - Protected routes
   - Automatic redirects
   - Cookie-based auth

---

## 📋 **SECURITY CHECKLIST**

### **Authentication** ✅
- [x] Password hashing (bcrypt)
- [x] Secure session management
- [x] HttpOnly cookies
- [x] SameSite protection
- [ ] ⚠️ Secure flag in production

### **Authorization** ⚠️
- [x] User authentication required
- [x] Session ownership verification
- [x] Proper 401/403 status codes
- [ ] ❌ `/agent/query` endpoint unprotected

### **Data Protection** ✅
- [x] User data isolation
- [x] Foreign key constraints
- [x] No SQL injection (parameterized queries)
- [x] No password storage in plaintext

### **Frontend Security** ✅
- [x] Protected routes
- [x] Auth context
- [x] Credentials sent with requests
- [x] Automatic logout on 401

---

## 🎯 **RECOMMENDATIONS**

### **Immediate (Required)**
1. **Fix `/agent/query` endpoint** - Add auth checks (CRITICAL)
2. **Add rate limiting** - Prevent brute force attacks
3. **Enable secure cookies** - For production deployment

### **Short Term (Important)**
4. **Add CORS validation** - Restrict allowed origins
5. **Implement session timeout** - Auto-logout after inactivity
6. **Add request logging** - Audit trail for security events
7. **Add input sanitization** - Prevent injection attacks

### **Long Term (Best Practices)**
8. **Add JWT tokens** - For better scalability
9. **Implement refresh tokens** - Longer sessions without re-login
10. **Add 2FA support** - Enhanced security
11. **Add IP whitelisting** - For admin endpoints
12. **Implement rate limiting per user** - Prevent abuse

---

## 📊 **OVERALL SECURITY RATING**

**Current State**: ⚠️ **6.5/10**

**Breakdown**:
- Authentication: 9/10 ✅
- Authorization: 4/10 ❌ (Critical issue in `/agent/query`)
- Session Management: 8/10 ✅
- Data Protection: 9/10 ✅
- Frontend Security: 8/10 ✅

**After Fixing Critical Issues**: 8.5/10 ✅

---

## 🔒 **CONCLUSION**

The authentication system is **well-implemented** with proper password hashing, session management, and user isolation. However, there is **ONE CRITICAL VULNERABILITY** in the `/agent/query` endpoint that allows unauthorized access to user data.

**Action Required**: 
1. ✅ Fix `/agent/query` endpoint immediately
2. ✅ Enable secure cookies for production
3. ✅ Consider implementing additional security layers

Once the critical issue is fixed, the system will have **strong security** suitable for production use.
