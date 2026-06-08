import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useNavigate, Routes, Route } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import UploadForm from "./components/UploadForm";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";

const API_BASE = "http://localhost:8000";

// Configure axios to send cookies with requests
axios.defaults.withCredentials = true;

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<MainContent />} />
      </Routes>
    </div>
  );
}

function MainContent() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState(null);
  const [schema, setSchema] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fileType, setFileType] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [currentConvId, setCurrentConvId] = useState(null);
  const messagesEndRef = useRef(null);

  // Group conversations by session_id and return one entry per session (latest by timestamp)
  const groupConversationsBySession = (convs) => {
    const map = {};
    convs.forEach((c) => {
      const sid = c.session_id || "";
      // keep the most recent conversation for the session
      if (!map[sid]) {
        map[sid] = { ...c, _count: 1 };
      } else {
        map[sid]._count = (map[sid]._count || 1) + 1;
        try {
          const a = new Date(c.timestamp);
          const b = new Date(map[sid].timestamp);
          if (!isNaN(a) && !isNaN(b) ? a > b : false) {
            map[sid] = { ...c, _count: map[sid]._count };
          }
        } catch (e) {
          // if parsing fails, prefer existing
        }
      }
    });
    return Object.values(map);
  };

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      navigate("/login");
    }
  }, [user, authLoading, navigate]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check system health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await axios.get(`${API_BASE}/get_system_health`);
        console.log("System health:", res.data);
      } catch (err) {
        console.error("Health check failed:", err);
      }
    };
    checkHealth();
  }, []);

  // Load conversations on mount
  // Load conversations on mount
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const res = await axios.get(`${API_BASE}/conversations`);
        console.log("Conversations loaded:", res.data);
        setConversations(groupConversationsBySession(res.data));
      } catch (err) {
        console.log("No conversations yet");
      }
    };
    loadConversations();
  }, []);

  // The upload logic is now centralized in the UploadForm component.
  // This placeholder is kept for backward compatibility but does nothing.
  const handleUpload = async () => {};

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMessage = { role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      // Determine endpoint based on file type
      // const endpoint = fileType === "pdf" ? "/query/rag" : "/query";
      const endpoint = "/chat"; // unified endpoint for both types
      
      const res = await axios.post(`${API_BASE}${endpoint}`, {
        session_id: sessionId,
        question: input
      });

      let assistantMessage;
      
      // Check for error response FIRST - before categorizing as RAG/SQL
      if (res.data.error || res.data.type === "error") {
        // Determine error type for better user feedback
        let errorType = "Error";
        let errorMessage = res.data.error || res.data.answer || "An error occurred";
        
        // Check for SQL-specific errors
        if (res.data.note && res.data.note.includes("SQL")) {
          errorType = "SQL Error";
          errorMessage = res.data.error || "SQL query failed";
        }
        // Check for RAG-specific errors
        else if (res.data.note && res.data.note.includes("RAG")) {
          errorType = "Document Search Error";
          errorMessage = res.data.error || "Document search failed";
        }
        // Check if it's a combined query with partial failure
        else if (res.data.type === "combined" && res.data.error) {
          errorType = "Combined Query Error";
        }
        
        assistantMessage = {
          role: "error",
          content: errorMessage,
          errorType: errorType,
          originalQuestion: input // Save the question that caused the error
        };
      } else if (fileType === "pdf") {
        // RAG response
        assistantMessage = {
          role: "assistant",
          content: res.data.answer,
          sources: res.data.sources,
          context_chunks: res.data.context_chunks,
          execution_time: res.data.execution_time_ms,
          type: "rag"
        };
      } else {
        // SQL response
        assistantMessage = {
          role: "assistant",
          content: res.data.sql_query,
          results: res.data.results,
          columns: res.data.columns,
          // summary: res.data.summary,
          execution_time: res.data.execution_time_ms,
          type: "sql"
        };
      }
      
      setMessages(prev => [...prev, assistantMessage]);
      
      // Save conversation to backend
      try {
        const saveRes = await axios.post(`${API_BASE}/conversations/save`, {
          session_id: sessionId,
          first_query: input,
          messages: [...messages, userMessage, assistantMessage]
        });
        console.log("Conversation saved:", saveRes.data);
        
        // Reload conversations to show the new one (grouped by session)
        const res = await axios.get(`${API_BASE}/conversations`);
        console.log("Conversations after save:", res.data);
        setConversations(groupConversationsBySession(res.data));
      } catch (err) {
        console.error("Failed to save conversation:", err);
      }
      
    } catch (err) {
      console.error("Query failed:", err);
      setMessages(prev => [
        ...prev,
        {
          role: "error",
          content: err.response?.data?.detail || "Query failed"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const renderMessage = (msg) => {
    if (msg.role === "user") {
      return (
        <div className="flex justify-end mb-4">
          <div className="bg-blue-600 text-white px-4 py-2 rounded-lg max-w-[80%]">
            {msg.content}
          </div>
        </div>
      );
    }
    
    if (msg.role === "system") {
      return (
        <div className="flex justify-center mb-4">
          <div className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm">
            {msg.content}
          </div>
        </div>
      );
    }
    
    if (msg.role === "error") {
      return (
        <div className="flex justify-start mb-4">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded-lg max-w-[80%]">
            {msg.content}
          </div>
        </div>
      );
    }

    // RAG response (PDF)
    if (msg.type === "rag") {
      return (
        <div className="flex justify-start mb-4">
          <div className="bg-white border border-gray-200 rounded-lg max-w-[90%] shadow-sm">
            <div className="bg-purple-100 px-4 py-2 rounded-t-lg">
              <span className="font-medium text-purple-700">Answer from Documents:</span>
            </div>
            <div className="p-4">
              <div className="text-gray-800 leading-relaxed">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            </div>
            
            {msg.execution_time && (
              <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
                Execution time: {msg.execution_time}ms
              </div>
            )}

            {msg.sources && msg.sources.length > 0 && (
              <div className="px-4 py-3 bg-purple-50 border-t border-purple-100 rounded-b-lg">
                <h4 className="font-medium text-purple-800 mb-2 text-sm">Sources:</h4>
                <ul className="text-xs text-purple-700 space-y-1">
                  {msg.sources.map((source, i) => (
                    <li key={i}>• {source}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      );
    }

    // Error response - handle type: "error" specifically
    if (msg.type === "error" || msg.role === "error") {
      return (
        <div className="flex justify-start mb-4">
          <div className="bg-red-50 border border-red-300 rounded-lg max-w-[90%] shadow-sm w-full">
            <div className="bg-red-100 px-4 py-2 rounded-t-lg flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-red-600" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="font-semibold text-red-800">{msg.errorType || "Error"}</span>
            </div>
            <div className="p-4">
              <p className="text-red-700">{msg.content || msg.error || msg.answer}</p>
              {msg.originalQuestion && (
                <div className="mt-3 pt-3 border-t border-red-200">
                  <p className="text-xs text-red-500 mb-1">Your question:</p>
                  <p className="text-sm text-red-600 italic">{msg.originalQuestion}</p>
                </div>
              )}
              {msg.note && (
                <div className="mt-2 text-xs text-red-500">
                  Note: {msg.note}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // SQL response (CSV)
    console.log("Messages count:", msg.length);
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-white border border-gray-200 rounded-lg max-w-[90%] shadow-sm">
          <div className="bg-gray-100 px-4 py-2 rounded-t-lg">
            <span className="font-medium text-gray-700">SQL Query:</span>
          </div>
          <div className="bg-gray-50 p-3">
            <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap">
              {msg.content}
            </pre>
          </div>
          
          {msg.execution_time && (
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 rounded-b-lg text-xs text-gray-500">
              Execution time: {msg.execution_time}ms
            </div>
          )}

          {msg.results && msg.results.length > 0 && (
            <div className="p-4 border-t border-gray-200">
              <h4 className="font-medium text-gray-700 mb-2">Results:</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-100">
                      {msg.columns?.map((col, i) => (
                        <th key={i} className="px-3 py-2 text-left font-medium text-gray-600">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {msg.results.slice(0, 10).map((row, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        {row.map((cell, j) => (
                          <td key={j} className="px-3 py-2 text-gray-700">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {msg.results.length > 10 && (
                  <p className="text-xs text-gray-500 mt-2">
                    Showing first 10 of {msg.results.length} rows
                  </p>
                )}
              </div>
            </div>
          )}

          {/* {msg.summary && (
            <div className="px-4 py-3 bg-blue-50 border-t border-blue-100">
              <h4 className="font-medium text-blue-800 mb-2">Insights:</h4>
              <div className="text-sm text-blue-900 leading-relaxed">
                <ReactMarkdown>{msg.summary}</ReactMarkdown>
              </div>
            </div>
          )} */}
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white p-4 shadow-lg">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">QueryMind</h1>
          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-3">
                <div className="text-sm">
                  <span className="text-blue-200">Username:</span> {user.username}
                </div>
                <button 
                  onClick={async () => {
                    try {
                      await axios.post(`${API_BASE}/auth/logout`);
                      localStorage.removeItem("sessionId");
                      localStorage.removeItem("userId");
                      setMessages([]);
                      setSessionId(null);
                      setSchema(null);
                      setFileType(null);
                      setCurrentConvId(null);
                      navigate("/login");
                    } catch (err) {
                      console.error("Logout failed:", err);
                    }
                  }}
                  className="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  Logout
                </button>
              </div>
            )}
            {/* {sessionId && (
              <div className="text-sm">
                <span className="text-blue-200">Session:</span> {sessionId.slice(0, 8)}...
              </div>
            )} */}
            {fileType && (
              <div className="text-sm">
                <span className="text-blue-200">Data Type:</span> {fileType.toUpperCase()}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="container mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-bold text-gray-800 mb-3">Upload Data</h2>
                <UploadForm sessionId={sessionId} setSessionId={setSessionId} setSchema={setSchema} setFileType={setFileType} />
              
              {schema && (
                <div className="mt-4">
                  {schema.schema && (
                    <div className="mb-4">
                      <h3 className="font-medium text-gray-700 mb-2">Loaded Tables:</h3>
                      <ul className="space-y-1 text-sm">
                        {Object.keys(schema.schema).map((table) => (
                          <li key={table} className="bg-gray-100 px-2 py-1 rounded">
                            {table}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {schema.files && schema.files.length > 0 && (
                    <div>
                      <h3 className="font-medium text-gray-700 mb-2">Loaded Files:</h3>
                      <ul className="space-y-1 text-sm">
                        {schema.files.map((file) => (
                          <li key={file} className="bg-gray-100 px-2 py-1 rounded">
                            {file}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {sessionId && (
              <div className="bg-white rounded-lg shadow p-4">
                <h2 className="font-bold text-gray-800 mb-3">Session Info</h2>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-gray-500">Session ID:</span>
                    <p className="font-mono text-xs break-all">{sessionId}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Data Type:</span>
                    <p>{fileType?.toUpperCase() || "Unknown"}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between items-center mb-3">
                <h2 className="font-bold text-gray-800">Conversations</h2>
                <button 
                  onClick={() => {
                    setMessages([]);
                    setSessionId(null);
                    setSchema(null);
                    setFileType(null);
                    setCurrentConvId(null);
                  }}
                  className="bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-1 rounded text-xs font-medium transition-colors"
                >
                  New Chat
                </button>
              </div>
              
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {conversations.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-2">No conversations yet</p>
                ) : (
                  conversations.map((conv) => (
                    <div 
                      key={conv.id}
                      onClick={async () => {
                        setCurrentConvId(conv.id);
                        setMessages(conv.messages);
                        setSessionId(conv.session_id);
                        // Load the schema or loaded file list for the selected session
                        try {
                          const schemaRes = await axios.get(`${API_BASE}/schema/${conv.session_id}`);
                          if (schemaRes.data) {
                            setFileType(schemaRes.data.file_type || "csv");
                            setSchema({
                              schema: schemaRes.data.schema || null,
                              files: schemaRes.data.files || null,
                            });
                          }
                        } catch (e) {
                          console.error('Failed to load schema for session', e);
                          setSchema(null);
                        }
                      }}
                      className={`group relative p-2 rounded cursor-pointer text-sm ${
                        currentConvId === conv.id ? 'bg-blue-100 text-blue-800' : 'hover:bg-gray-100'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            // Delete ALL conversations for this session
                            await axios.delete(`${API_BASE}/conversations/${conv.id}?session_id=${conv.session_id}`);
                            // Reload conversations from backend to keep grouped view accurate
                            const res = await axios.get(`${API_BASE}/conversations`);
                            setConversations(groupConversationsBySession(res.data));
                            if (currentConvId === conv.id) {
                              setCurrentConvId(null);
                              setMessages([]);
                              setSessionId(null);
                              setSchema(null);
                              setFileType(null);
                            }
                          } catch (err) {
                            console.error('Failed to delete conversation:', err);
                            alert('Could not delete conversation.');
                          }
                        }}
                        className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity text-red-500 hover:text-red-700"
                        title="Delete all conversations in this session"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                          <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H3.5A1.5 1.5 0 002 5.5v1A.5.5 0 002.5 7h15a.5.5 0 00.5-.5v-1A1.5 1.5 0 0016.5 4H15V3a1 1 0 00-1-1H6zm1 4a.5.5 0 00-.5.5V15a1 1 0 001 1h5a1 1 0 001-1V6.5A.5.5 0 0012 6H7zm1 1h1v7H8V7zm3 0h1v7h-1V7z" clipRule="evenodd" />
                        </svg>
                      </button>
                      <div className="truncate">{conv.first_query}</div>
                      <div className="text-xs text-gray-500 mt-1">{conv.timestamp}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Chat Area */}
          <div className="lg:col-span-2 flex flex-col h-[calc(100vh-120px)]">
            <div className="flex-1 overflow-y-auto bg-white rounded-lg shadow p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 mt-20">
                  {sessionId ? (
                    <>
                      <p className="text-lg mb-2">Ready to ask questions!</p>
                      <p>Upload data or ask about your session.</p>
                    </>
                  ) : (
                    <>
                      <p className="text-lg mb-2">Welcome to QueryMind</p>
                      <p>Upload a CSV or PDF file to get started.</p>
                    </>
                  )}
                </div>
              ) : (
                messages.map((msg, i) => (
                  <div key={i}>{renderMessage(msg)}</div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="mt-4">
              <form onSubmit={handleQuery} className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={sessionId ? "Ask a question about your data..." : "Upload data first..."}
                  disabled={!sessionId || loading}
                  className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || !sessionId || loading}
                  className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? "..." : "Send"}
                </button>
              </form>
              {!sessionId && (
                <p className="text-center text-sm text-red-500 mt-2">
                  Please upload a file first to start querying
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
