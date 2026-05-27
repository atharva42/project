import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useNavigate, Routes, Route } from "react-router-dom";
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
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const res = await axios.get(`${API_BASE}/conversations`);
        console.log("Conversations loaded:", res.data);
        setConversations(res.data);
      } catch (err) {
        console.log("No conversations yet");
      }
    };
    loadConversations();
  }, []);

  const handleUpload = async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      setSessionId(res.data.session_id);
      setFileType(res.data.file_type);
      
      if (res.data.schema) {
        setSchema(res.data.schema);
      }
      
      // Add system message
      setMessages(prev => [
        ...prev,
        {
          role: "system",
          content: `${res.data.file_type.toUpperCase()} file uploaded successfully! Session ID: ${res.data.session_id.slice(0, 8)}...`
        }
      ]);
      
    } catch (err) {
      console.error("Upload failed:", err);
      alert("Upload failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMessage = { role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      // Determine endpoint based on file type
      const endpoint = fileType === "pdf" ? "/query/rag" : "/query";
      
      const res = await axios.post(`${API_BASE}${endpoint}`, {
        session_id: sessionId,
        question: input
      });

      let assistantMessage;
      
      if (fileType === "pdf") {
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
          summary: res.data.summary,
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
        
        // Reload conversations to show the new one
        const res = await axios.get(`${API_BASE}/conversations`);
        console.log("Conversations after save:", res.data);
        setConversations(res.data);
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
              <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>
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

    // SQL response (CSV)
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

          {msg.summary && (
            <div className="px-4 py-3 bg-blue-50 border-t border-blue-100">
              <h4 className="font-medium text-blue-800 mb-2">Insights:</h4>
              <p className="text-sm text-blue-900 leading-relaxed">
                {msg.summary}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white p-4 shadow-lg">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">DataSensei</h1>
          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-3">
                <div className="text-sm">
                  <span className="text-blue-200">User:</span> {user.username}
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
            {sessionId && (
              <div className="text-sm">
                <span className="text-blue-200">Session:</span> {sessionId.slice(0, 8)}...
              </div>
            )}
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
              <UploadForm setSessionId={setSessionId} setSchema={setSchema} setFileType={setFileType} />
              
              {schema && (
                <div className="mt-4">
                  <h3 className="font-medium text-gray-700 mb-2">Loaded Tables:</h3>
                  <ul className="space-y-1 text-sm">
                    {Object.keys(schema).map((table) => (
                      <li key={table} className="bg-gray-100 px-2 py-1 rounded">
                        {table}
                      </li>
                    ))}
                  </ul>
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
                      onClick={() => {
                        setCurrentConvId(conv.id);
                        setMessages(conv.messages);
                        setSessionId(conv.session_id);
                      }}
                      className={`p-2 rounded cursor-pointer text-sm ${
                        currentConvId === conv.id ? 'bg-blue-100 text-blue-800' : 'hover:bg-gray-100'
                      }`}
                    >
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
                      <p className="text-lg mb-2">Welcome to DataSensei</p>
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
