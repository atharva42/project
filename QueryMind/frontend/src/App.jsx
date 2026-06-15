import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useNavigate, Routes, Route } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import UploadForm from "./components/UploadForm";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import config from "./config";

const API_BASE = config.API_BASE_URL;

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
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState(null);
  const [schema, setSchema] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fileType, setFileType] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [currentConvId, setCurrentConvId] = useState(null);
  const [expandedResults, setExpandedResults] = useState({}); // Track expanded state per message
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
        await axios.get(`${API_BASE}/get_system_health`);
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
        setConversations(groupConversationsBySession(res.data));
      } catch (err) {
        // no conversations yet
      }
    };
    loadConversations();
  }, []);

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery(e);
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMessage = { role: "user", content: input };
    
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    // Add a dynamic loading message that updates
    const loadingMessageId = Date.now();
    const loadingMessage = { 
      role: "loading", 
      content: "Routing your question...", 
      id: loadingMessageId 
    };
    
    setTimeout(() => setMessages(prev => [...prev, loadingMessage]), 100);

    // Simulate loading stages
    const stages = [
      "Routing your question...",
      "Analyzing data sources...", 
      "Generating response...",
      "Finalizing answer..."
    ];
    
    let stageIndex = 0;
    const stageInterval = setInterval(() => {
      stageIndex = (stageIndex + 1) % stages.length;
      const newStage = stages[stageIndex];

      setMessages(prev => prev.map(msg => 
        msg.id === loadingMessageId 
          ? { ...msg, content: newStage }
          : msg
      ));
    }, 1500);

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
      } else {
        // Check if it's a combined response from the new agent
        if (res.data.type === "combined") {
          assistantMessage = {
            role: "assistant",
            content: res.data.answer,
            sql_result: res.data.sql_result,
            rag_result: res.data.rag_result,
            route: res.data.route,
            type: "combined"
          };
        } else if (fileType === "pdf" || res.data.type === "rag") {
          // RAG response
          assistantMessage = {
            role: "assistant",
            content: res.data.answer,
            sources: res.data.sources,
            context_chunks: res.data.context_chunks,
            execution_time: res.data.execution_time_ms,
            has_results: res.data.has_results !== false,
            route: res.data.route,
            type: "rag"
          };
        } else {
          // SQL response
          assistantMessage = {
            role: "assistant",
            content: res.data.sql_query,
            results: res.data.results,
            columns: res.data.columns || res.data.tables_used,
            execution_time: res.data.execution_time_ms,
            result_count: res.data.result_count,
            has_results: res.data.has_results !== false,
            route: res.data.route,
            type: "sql"
          };
        }
      }
      
      setMessages(prev => {
        // Remove the loading message and add the actual response
        const withoutLoading = prev.filter(msg => msg.role !== "loading");
        return [...withoutLoading, assistantMessage];
      });
      
      // Clear the loading stage interval
      clearInterval(stageInterval);
      
      // Save conversation to backend
      try {
        // Use the first user message as the title (first_query)
        const firstUserMessage = messages.find(m => m.role === "user")?.content || input;
        await axios.post(`${API_BASE}/conversations/save`, {
          session_id: sessionId,
          first_query: firstUserMessage,
          messages: [...messages, userMessage, assistantMessage]
        });
        
        // Reload conversations to show the new one (grouped by session)
        const res = await axios.get(`${API_BASE}/conversations`);
        setConversations(groupConversationsBySession(res.data));
      } catch (err) {
        console.error("Failed to save conversation:", err);
      }
      
    } catch (err) {
      console.error("Query failed:", err);
      const errorMessage = {
        role: "error",
        content: err.response?.data?.detail || "Query failed"
      };
      setMessages(prev => {
        // Remove the loading message and add the error
        const withoutLoading = prev.filter(msg => msg.role !== "loading");
        return [...withoutLoading, errorMessage];
      });
      
      // Clear the loading stage interval
      clearInterval(stageInterval);
    } finally {
      setLoading(false);
    }
  };

  const renderMessage = (msg, msgIndex) => {
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

    if (msg.role === "loading") {
      return (
        <div className="flex justify-start mb-4">
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 max-w-[80%] flex items-center space-x-3 shadow-sm">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
            </div>
            <div className="text-gray-700 text-sm">
              <div className="flex items-center space-x-2">
                <svg className="animate-spin h-4 w-4 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="font-medium text-blue-800">{msg.content}</span>
              </div>
              <div className="text-xs text-blue-600 mt-1">
                QueryMind is working on your request
              </div>
            </div>
          </div>
        </div>
      );
    }

    // Combined response (from LangGraph agent)
    if (msg.type === "combined") {
      return (
        <div className="flex justify-start mb-4">
          <div className="bg-white border border-gray-200 rounded-lg max-w-[90%] shadow-sm">
            <div className="bg-gradient-to-r from-purple-100 to-blue-100 px-4 py-2 rounded-t-lg">
              <span className="font-medium text-purple-700">Combined Analysis:</span>
            </div>
            <div className="p-4">
              <div className="text-gray-800 leading-relaxed">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
              
              {/* Show SQL and RAG details in expandable sections */}
              <div className="mt-4 space-y-2">
                {msg.sql_result && (
                  <details className="border rounded p-2">
                    <summary className="cursor-pointer font-medium text-gray-700">Database Query Details</summary>
                    <div className="mt-2 text-sm">
                      <pre className="bg-gray-100 p-2 rounded text-xs">{msg.sql_result.sql_query}</pre>
                      {msg.sql_result.results && msg.sql_result.results.length > 0 && (
                        <p className="mt-1 text-gray-600">{msg.sql_result.results.length} rows found</p>
                      )}
                    </div>
                  </details>
                )}
                {msg.rag_result && (
                  <details className="border rounded p-2">
                    <summary className="cursor-pointer font-medium text-gray-700">Document Sources</summary>
                    <div className="mt-2 text-sm">
                      {msg.rag_result.sources && msg.rag_result.sources.length > 0 && (
                        <ul className="text-gray-600">
                          {msg.rag_result.sources.map((source, i) => (
                            <li key={i}>• {source}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </details>
                )}
              </div>
            </div>
            
            {/* Route info */}
            {msg.route && (
              <div className="px-4 py-2 bg-gradient-to-r from-purple-50 to-blue-50 border-t border-gray-200 rounded-b-lg">
                <span className="text-xs text-purple-600 font-medium">
                  Route used: {msg.route.toUpperCase()}
                </span>
              </div>
            )}
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
              
              {/* Show no results message if applicable */}
              {msg.has_results === false && (
                <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <svg className="h-5 w-5 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    <span className="font-medium text-yellow-800">No relevant information found</span>
                  </div>
                  <p className="text-sm text-yellow-700 mt-1">
                    Try rephrasing your question or check if the information exists in your documents.
                  </p>
                </div>
              )}
            </div>

            {msg.sources && msg.sources.length > 0 && (
              <div className="px-4 py-3 bg-purple-50 border-t border-purple-100">
                <h4 className="font-medium text-purple-800 mb-2 text-sm">Sources:</h4>
                <ul className="text-xs text-purple-700 space-y-1">
                  {msg.sources.map((source, i) => (
                    <li key={i}>• {source}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Execution time and route info */}
            <div className="px-4 py-2 bg-purple-50 border-t border-purple-100 rounded-b-lg flex justify-between items-center">
              {msg.execution_time && (
                <span className="text-xs text-purple-600">
                  Executed in {msg.execution_time}ms
                </span>
              )}
              {msg.route && (
                <span className="text-xs text-purple-600 font-medium">
                  Route: {msg.route.toUpperCase()}
                </span>
              )}
            </div>
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

          {/* Handle empty results */}
          {msg.has_results === false || (msg.results && msg.results.length === 0) ? (
            <div className="p-4 border-t border-gray-200">
              <div className="flex items-center space-x-2 text-yellow-600 mb-2">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <span className="font-medium">No Results Found</span>
              </div>
              <p className="text-gray-600 text-sm">
                Your query executed successfully but returned no data. This could mean:
              </p>
              <ul className="text-sm text-gray-600 mt-2 ml-4 space-y-1">
                <li>• The filters are too restrictive</li>
                <li>• The data you're looking for doesn't exist</li>
                <li>• Try modifying your question or using different criteria</li>
              </ul>
              
              {msg.columns && msg.columns.length > 0 && (
                <div className="mt-3 p-2 bg-gray-100 rounded">
                  <p className="text-xs text-gray-500 mb-1">Available columns in query:</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.columns.map((col, i) => (
                      <span key={i} className="bg-white px-2 py-1 rounded text-xs text-gray-700 border">
                        {col}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Show results if they exist
            msg.results && msg.results.length > 0 && (
              <div className="p-4 border-t border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-gray-700">Results:</h4>
                  <span className="text-sm text-gray-500">
                    {msg.result_count || msg.results.length} row{(msg.result_count || msg.results.length) !== 1 ? 's' : ''} found
                  </span>
                </div>
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
                      {(expandedResults[msgIndex] ? msg.results : msg.results.slice(0, 10)).map((row, i) => (
                        <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                          {row.map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-gray-700">
                              {cell !== null && cell !== undefined ? String(cell) : (
                                <span className="text-gray-400 italic">null</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {msg.results.length > 10 && (
                    <div className="flex items-center justify-center mt-3">
                      <button 
                        onClick={() => {
                          setExpandedResults(prev => ({
                            ...prev,
                            [msgIndex]: !prev[msgIndex]
                          }));
                        }}
                        className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors flex items-center space-x-2"
                      >
                        {expandedResults[msgIndex] ? (
                          <>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                            <span>Show less</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                            <span>Show all {msg.results.length} rows</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          )}
          
          {/* Execution time and route info */}
          <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 rounded-b-lg flex justify-between items-center">
            {msg.execution_time && (
              <span className="text-xs text-gray-500">
                Executed in {msg.execution_time}ms
              </span>
            )}
            {msg.route && (
              <span className="text-xs text-blue-600 font-medium">
                Route used: {msg.route.toUpperCase()}
              </span>
            )}
          </div>
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
                    // Clear app-local state, then delegate to the auth
                    // context's logout() which posts /auth/logout, resets
                    // the auth user (setUser(null)) and navigates to /login.
                    setMessages([]);
                    setSessionId(null);
                    setSchema(null);
                    setFileType(null);
                    setCurrentConvId(null);
                    await logout();
                  }}
                  className="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  Logout
                </button>
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
                  <div key={i}>{renderMessage(msg, i)}</div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="mt-4">
              <form onSubmit={handleQuery} className="flex items-end gap-2">
                <textarea
                  rows={1}
                  value={input}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    if (newValue.length <= 1000) { // Character limit
                      setInput(newValue);
                    }
                    // Auto-resize textarea
                    e.target.style.height = 'auto';
                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                  }}
                  onKeyPress={handleKeyPress}
                  placeholder={
                    loading ? "QueryMind is processing..." :
                    sessionId ? "Ask a question about your data..." : 
                    "Upload data first..."
                  }
                  disabled={!sessionId || loading}
                  className={`flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none ${
                    loading ? 'bg-gray-50 border-gray-200 cursor-not-allowed' : 
                    !sessionId ? 'bg-gray-100' : 
                    'bg-white hover:border-gray-400'
                  }`}
                  style={{ minHeight: '48px' }}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || !sessionId || loading}
                  className={`w-12 h-12 rounded-lg font-medium transition-all flex items-center justify-center flex-shrink-0 ${
                    loading ? 'bg-gray-400 cursor-not-allowed' :
                    (!input.trim() || !sessionId) ? 'bg-gray-400 cursor-not-allowed' :
                    'bg-blue-600 hover:bg-blue-700 text-white hover:shadow-lg'
                  }`}
                >
                  {loading ? (
                    <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </button>
              </form>
              {!sessionId && (
                <p className="text-center text-sm text-red-500 mt-2">
                  Please upload a file first to start querying
                </p>
              )}
              {loading && (
                <div className="text-center text-sm text-blue-500 mt-2 flex items-center justify-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce"></div>
                    <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                  <span>QueryMind is working on your request...</span>
                </div>
              )}
              <div className="flex items-center justify-between text-xs text-gray-400 mt-2">
                <span>Press Enter to send • Shift+Enter for new line</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
