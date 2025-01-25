import React, { createContext, useState, useEffect } from "react";

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [userId, setUserId] = useState(() => localStorage.getItem("userId"));
  const [username, setUsername] = useState(() => localStorage.getItem("username"));
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [color, setColor] = useState(() => localStorage.getItem("color")); // Add color state

  useEffect(() => {
    const checkAuth = async () => {
      const storedToken = localStorage.getItem("token");
      console.log("🚀 ~ checkAuth ~ storedToken:", storedToken);
      if (!storedToken) {
        console.log("No token found. User not authenticated.");
        setToken(null);
        setUserId(null);
        setUsername(null);
        setColor(null); // Clear color
        return;
      }

      try {
        const response = await fetch(`${window.location.protocol}//rbiz.pro/api/check-login`, {
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
          setColor(data.color); // Set color

          // Persist in localStorage
          localStorage.setItem("userId", data.userId);
          localStorage.setItem("username", data.username);
          localStorage.setItem("token", storedToken);
          localStorage.setItem("color", data.color); // Persist color
        } else {
          console.log("Token invalid or expired. Logging out...");
          setToken(null);
          setUserId(null);
          setUsername(null);
          setColor(null); // Clear color

          // Clear from localStorage
          localStorage.removeItem("userId");
          localStorage.removeItem("username");
          localStorage.removeItem("token");
          localStorage.removeItem("color");
        }
      } catch (error) {
        console.error("Error checking authentication state:", error);
      }
    };

    checkAuth();
  }, []);  

  const logout = async (callback) => {
    try {
      const response = await fetch(`${window.location.protocol}//rbiz.pro/api/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`, // Include token in headers for logout
        },
      });
  
      if (response.ok) {
        setUserId(null);
        setUsername("");
        setToken(null);
        setColor(null); // Clear color
  
        // Clear from localStorage
        localStorage.removeItem("userId");
        localStorage.removeItem("username");
        localStorage.removeItem("token");
        localStorage.removeItem("color");
  
        if (callback) callback(); // Execute the callback, e.g., close modal
      } else {
        console.error("Failed to log out.");
      }
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };
  

  return (
    <AuthContext.Provider
      value={{ userId, username, token, color, setUserId, setUsername, setToken, setColor, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};
