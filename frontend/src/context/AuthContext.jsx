import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { loginUser, registerUser, getMe, clearAuth, setAuthToken, getAuthToken, logoutUser } from "../api/client";

const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize auth state on mount (check localStorage for token)
  useEffect(() => {
    const storedToken = localStorage.getItem("atlas_auth_token");
    const storedUser = localStorage.getItem("atlas_auth_user");

    if (storedToken && storedUser) {
      setToken(storedToken);
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("atlas_auth_user");
      }
    }
    setLoading(false);
  }, []);

  // Login function - calls backend
  const login = useCallback(async (email, password) => {
    try {
      const response = await loginUser(email, password);
      const { access_token, user: userData } = response;

      // Store token and user
      setAuthToken(access_token);
      localStorage.setItem("atlas_auth_user", JSON.stringify(userData));
      setToken(access_token);
      setUser(userData);

      return true;
    } catch (error) {
      console.error("Login failed:", error);
      return false;
    }
  }, []);

  // Register function - calls backend
  const register = useCallback(async (email, fullName, password, passwordConfirm) => {
    try {
      const response = await registerUser(email, fullName, password, passwordConfirm);
      const { access_token, user: userData } = response;

      // Store token and user
      setAuthToken(access_token);
      localStorage.setItem("atlas_auth_user", JSON.stringify(userData));
      setToken(access_token);
      setUser(userData);

      return true;
    } catch (error) {
      console.error("Registration failed:", error);
      // Return the backend's error detail so the page can show the real
      // reason (e.g. duplicate email, password policy) instead of a generic
      // message. Success returns `true`; any other return value is the
      // error message.
      return error?.message || "Registration failed. Please try again.";
    }
  }, []);

  // Logout function
  const logout = useCallback(async () => {
    const currentToken = getAuthToken();
    if (currentToken) {
      try {
        await logoutUser(currentToken);
      } catch {
        // Ignore logout API errors
      }
    }
    clearAuth();
    setToken(null);
    setUser(null);
  }, []);

  // Get current token for API calls
  const getToken = useCallback(() => {
    return token || localStorage.getItem("atlas_auth_token");
  }, [token]);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    getToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
