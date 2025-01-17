import React, { useState, useEffect, useContext, useCallback } from "react";
import { FixedSizeGrid as Grid } from "react-window";
import { AuthContext } from "../contexts/AuthContext";
import "../styles/CellGrid.css";
import "../styles/Login.css";

const CellGrid = ({ gridSize = 2000, cellSize = 20 }) => {
  const { userId, username, setUserId, setUsername, logout } = useContext(AuthContext);
  const [grid, setGrid] = useState({});
  const [hoveredFortLevel, setHoveredFortLevel] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [loginStep, setLoginStep] = useState("getPassword");
  const [loginCode, setLoginCode] = useState("");
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(true);

  // Fetch grid data
  useEffect(() => {
    const fetchGrid = async () => {
      try {
        const response = await fetch("http://127.0.0.1:5000/get-grid");
        const data = await response.json();

        const gridData = {};
        data.forEach((cell) => {
          gridData[cell.coordinates] = cell;
        });

        setGrid(gridData);
      } catch (error) {
        console.error("Error fetching grid:", error);
      }
    };

    fetchGrid();
  }, []);

  // Restore authentication state
  useEffect(() => {
    const restoreAuthState = async () => {
      try {
        const response = await fetch("http://127.0.0.1:5000/check-login", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setUserId(data.userId);
          setUsername(data.username);
        } else {
          setUserId(null);
          setUsername("");
          console.log("User is not logged in");
        }
      } catch (error) {
        console.error("Error restoring authentication state:", error);
      } finally {
        setLoading(false);
      }
    };

    restoreAuthState();
  }, [setUserId, setUsername, userId]);

  // Request login code
  const requestLoginCode = async () => {
    setIsRequestingCode(true);
    try {
      const response = await fetch("http://127.0.0.1:5000/request-login-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: identifier.trim() }),
      });

      if (response.ok) {
        alert("Code sent to your Telegram account.");
        setLoginStep("verifyPassword");
      } else {
        const errorData = await response.json();
        console.error("Error requesting login code:", errorData.error);
        alert("Failed to send code. Check your identifier and try again.");
      }
    } catch (error) {
      console.error("Error requesting login code:", error);
      alert("An error occurred. Please try again.");
    } finally {
      setIsRequestingCode(false);
    }
  };

  // Verify login code
  const verifyLoginCode = async () => {
    try {
      const response = await fetch("http://127.0.0.1:5000/verify-login-code", {
        method: "POST",
        body: JSON.stringify({ identifier: identifier.trim(), code: loginCode.trim() }),
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("token", data.token);
        setUserId(data.userId);
        setUsername(data.username);
        setIsLoginModalOpen(false);
      } else {
        const errorData = await response.json();
        console.error("Error verifying login code:", errorData.error);
        alert("Invalid code or identifier. Please try again.");
      }
    } catch (error) {
      console.error("Error verifying login code:", error);
      alert("An error occurred. Please try again.");
    }
  };

  const handleMouseEnter = (event, cell) => {
    if (cell.is_border && cell.fort_level !== undefined) {
      setHoveredFortLevel(cell.fort_level);
      setTooltipPosition({
        top: event.clientY + 10,
        left: event.clientX + 10,
      });
    }
  };

  const handleMouseLeave = () => {
    setHoveredFortLevel(null);
  };

  // Use callback to always access the latest userId
  const handleCellClick = useCallback(
    async (row, col) => {
      if (!userId) {
        alert("You must be logged in to claim a cell.");
        return;
      }

      try {
        const response = await fetch("http://127.0.0.1:5000/claim-cell", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
          body: JSON.stringify({ row, col, userId }),
        });

        if (response.ok) {
          const updatedGrid = await fetch("http://127.0.0.1:5000/get-grid");
          const data = await updatedGrid.json();

          const gridData = {};
          data.forEach((cell) => {
            gridData[cell.coordinates] = cell;
          });

          setGrid(gridData);
        } else {
          const errorData = await response.json();
          console.error("Error claiming cell:", errorData.error);
        }
      } catch (error) {
        console.error("Error sending cell claim request:", error);
      }
    },
    [userId]
  );

  const renderLoginModalContent = () => {
    if (loginStep === "getPassword") {
      return (
        <>
          <h2>Login</h2>
          <input
            type="text"
            placeholder="Enter your username or Telegram ID"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
          />
          <button onClick={requestLoginCode} disabled={isRequestingCode}>
            {isRequestingCode ? "Sending..." : "Get Password"}
          </button>
        </>
      );
    } else if (loginStep === "verifyPassword") {
      return (
        <>
          <h2>Enter Password</h2>
          <input
            type="text"
            placeholder="Enter the code sent to your Telegram"
            value={loginCode}
            onChange={(e) => setLoginCode(e.target.value)}
          />
          <button onClick={verifyLoginCode}>Login</button>
        </>
      );
    }
  };

  const Cell = ({ columnIndex, rowIndex, style }) => {
    const cellKey = `${rowIndex}-${columnIndex}`;
    const cell = grid[cellKey] || {};

    return (
      <div
        style={{
          ...style,
          width: `${cellSize}px`,
          height: `${cellSize}px`,
        }}
        className={`cell ${
          cell.is_border ? "cell-border" : ""
        } ${cell.is_inner ? "cell-inner" : ""} ${
          cell.user_id ? "cell-owned" : ""
        }`}
        onClick={() => handleCellClick(rowIndex, columnIndex)}
        onMouseEnter={(event) => handleMouseEnter(event, cell)}
        onMouseLeave={handleMouseLeave}
      >
        {cell.level !== undefined && <div className="cell-level">{cell.level}</div>}
      </div>
    );
  };

  if (loading) {
    return <div className="loading-indicator">Loading...</div>;
  }

  return (
    <div className="grid-scrollable">
      <button
        className="login-button"
        onClick={() => (username ? setIsLogoutModalOpen(true) : setIsLoginModalOpen(true))}
      >
        {username ? username : "Login"}
      </button>

      {isLoginModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            {renderLoginModalContent()}
            <button onClick={() => setIsLoginModalOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {isLogoutModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Welcome, {username}</h2>
            <button onClick={logout} className="logout-button">
              Logout
            </button>
            <button onClick={() => setIsLogoutModalOpen(false)}>Cancel</button>
          </div>
        </div>
      )}

      {hoveredFortLevel !== null && (
        <div
          className="tooltip"
          style={{
            top: `${tooltipPosition.top}px`,
            left: `${tooltipPosition.left}px`,
          }}
        >
          Fort Level: {hoveredFortLevel}
        </div>
      )}
      <Grid
        columnCount={gridSize}
        rowCount={gridSize}
        columnWidth={cellSize}
        rowHeight={cellSize}
        height={window.innerHeight}
        width={window.innerWidth}
        itemData={grid}
      >
        {Cell}
      </Grid>
    </div>
  );
};

export default CellGrid;
