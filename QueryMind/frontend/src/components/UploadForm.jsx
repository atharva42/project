import React, { useState } from "react";
import axios from "axios";

const API_BASE = "http://localhost:8000";

function UploadForm({ setSessionId, setSchema, setFileType }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionId, setLocalSessionId] = useState(setSessionId ? null : "");
  const fileInputRef = React.useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      setSessionId(res.data.session_id);
      setFileType(res.data.file_type);
      
      // Only set schema for CSV files
      if (res.data.schema) {
        setSchema(res.data.schema);
      }
      
      // Clear file input
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
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
