import React, { createContext, useContext, useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import config from "../config";

const API_BASE = config.API_BASE_URL;

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await axios.get(`${API_BASE}/auth/status`);
        if (response.data.authenticated) {
          setUser(response.data.user);
        }
      } catch (err) {
        console.error("Auth check failed:", err);
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (username, password) => {
    const response = await axios.post(`${API_BASE}/auth/login`, {
      username,
      password,
    });
    
    // Fetch user data after login
    const statusResponse = await axios.get(`${API_BASE}/auth/status`);
    if (statusResponse.data.authenticated) {
      setUser(statusResponse.data.user);
    }
    
    return response.data;
  };

  const register = async (username, password) => {
    const response = await axios.post(`${API_BASE}/auth/register`, {
      username,
      password,
    });
    return response.data;
  };

  const logout = async () => {
    try {
      await axios.post(`${API_BASE}/auth/logout`);
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      setUser(null);
      navigate("/login");
    }
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
