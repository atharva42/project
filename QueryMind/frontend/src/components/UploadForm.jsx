import React, { useState } from "react";
import axios from "axios";
import config from "../config";

const API_BASE = config.API_BASE_URL;
function UploadForm({ sessionId, setSessionId, setSchema, setFileType, isDemoSession }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = React.useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      // Include the existing session ID (if any) so the backend can append to the same session.
      // TEMPORARY DEMO FEATURE: never append to a shared demo session — start a
      // fresh user-owned session instead so per-user isolation is preserved.
      // Remove `&& !isDemoSession` (and the prop) when removing the demo feature.
      const appendToSession = sessionId && !isDemoSession;
      const uploadUrl = appendToSession ? `${API_BASE}/upload?session_id=${sessionId}` : `${API_BASE}/upload`;
      const res = await axios.post(uploadUrl, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      // Store the session ID returned from the backend for future uploads
      const newSessionId = res.data.session_id;
      setSessionId(newSessionId);
      setFileType(res.data.file_type);

      // TEMPORARY DEMO FEATURE: when uploading away from a demo session, drop the
      // demo's schema so it isn't merged into the new session's display.
      if (isDemoSession) {
        setSchema(null);
      }
      
      // Merge schema and file metadata for the current session
      setSchema(prev => {
        const next = {
          schema: prev?.schema || null,
          files: prev?.files || null,
        };

        if (res.data.schema) {
          next.schema = {
            ...(next.schema || {}),
            ...res.data.schema,
          };
        }
        // Backend always returns the complete, authoritative list of files
        // So we replace (not append) to avoid duplicates
        if (res.data.files) {
          next.files = res.data.files;
        }

        if (!next.schema && !next.files) {
          return null;
        }
        return next;
      });
      
      // Clear file input
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      
      // Show feedback for duplicate uploads
      if (res.data.already_exists) {
        alert(`File "${file.name}" was already uploaded to this session. No new embeddings created.`);
      }
    } catch (err) {
      console.error(err);
      alert("Upload failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mb-4">
      <label className="block mb-2 font-medium">Upload CSV or PDF:</label>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.pdf"
        onChange={(e) => setFile(e.target.files[0])}
        className="border p-2 rounded w-full mb-2"
      />
      {file && (
        <div className="flex items-center justify-between gap-2 mb-2 px-2 py-2 bg-yellow-50 border border-yellow-200 rounded">
          <span className="text-sm text-yellow-900 truncate">Selected: {file.name}</span>
          <button
            type="button"
            onClick={() => {
              setFile(null);
              if (fileInputRef.current) {
                fileInputRef.current.value = "";
              }
            }}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Remove
          </button>
        </div>
      )}
      <button
        type="submit"
        disabled={loading || !file}
        className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
      >
        {loading ? "Uploading..." : "Upload"}
      </button>
    </form>
  );
}

export default UploadForm;
