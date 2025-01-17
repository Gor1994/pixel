import React, { createContext, useState, useEffect } from "react";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [userId, setUserId] = useState(() => localStorage.getItem("userId"));
  const [username, setUsername] = useState(() => localStorage.getItem("username"));
  const [token, setToken] = useState(() => localStorage.getItem("token")); // Add token state
  
  useEffect(() => {
    const checkAuth = async () => {
      const storedToken = localStorage.getItem("token");
      console.log("🚀 ~ checkAuth ~ storedToken:", storedToken)
      if (!storedToken) {
        console.log("No token found. User not authenticated.");
        setToken(null);
        setUserId(null);
        setUsername(null);
        return;
      }
  
      try {
        const response = await fetch("http://127.0.0.1:5000/check-login", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${storedToken}`, // Include token in headers
          },
        });
  
        if (response.ok) {
          const data = await response.json();
          setUserId(data.userId);
          setUsername(data.username);
          setToken(storedToken); // Keep the stored token
  
          // Persist in localStorage
          localStorage.setItem("userId", data.userId);
          localStorage.setItem("username", data.username);
        } else {
          console.log("Token invalid or expired. Logging out...");
          setToken(null);
          setUserId(null);
          setUsername(null);
  
          // Clear from localStorage
          localStorage.removeItem("userId");
          localStorage.removeItem("username");
          localStorage.removeItem("token");
        }
      } catch (error) {
        console.error("Error checking authentication state:", error);
      }
    };
  
    checkAuth();
  }, []);
  

  const login = async (identifier, loginCode) => {
    try {
      const response = await fetch("http://127.0.0.1:5000/verify-login-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, loginCode }),
      });

      if (response.ok) {
        const data = await response.json();
        setUserId(data.userId);
        setUsername(data.username);
        setToken(data.token);

        // Persist in localStorage
        localStorage.setItem("userId", data.userId);
        localStorage.setItem("username", data.username);
        localStorage.setItem("token", data.token);
        return true;
      } else {
        const errorData = await response.json();
        console.error("Error logging in:", errorData.error);
        return false;
      }
    } catch (error) {
      console.error("Error during login:", error);
      return false;
    }
  };

  const logout = async () => {
    try {
      const response = await fetch("http://127.0.0.1:5000/logout", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`, // Include token in headers for logout
        },
      });

      if (response.ok) {
        setUserId(null);
        setUsername("");
        setToken(null);

        // Clear from localStorage
        localStorage.removeItem("userId");
        localStorage.removeItem("username");
        localStorage.removeItem("token");
      } else {
        console.error("Failed to log out.");
      }
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };

  return (
    <AuthContext.Provider
      value={{ userId, username, token, setUserId, setUsername, setToken, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};
