import React, { useState, useEffect, useContext, useCallback } from "react";
import { FixedSizeGrid as Grid } from "react-window";
import { AuthContext } from "../contexts/AuthContext";
import "../styles/CellGrid.css";
import "../styles/Login.css";
import { io } from "socket.io-client";

// const socket = io("ws://rbiz.pro");
const socket = io("ws://rbiz.pro", {
  transports: ["websocket"], // Force WebSocket transport
  upgrade: true,
});



const CellGrid = ({ gridSize = 2000, cellSize = 20 }) => {
  const { userId, username, setUserId, setUsername, logout } = useContext(AuthContext);
  const [grid, setGrid] = useState({});
  const [hoveredFortLevel, setHoveredFortLevel] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [loginStep, setLoginStep] = useState("getPassword");
  const [loginCode, setLoginCode] = useState("");
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(true);
  const [energy, setEnergy] = useState({ charges: 0, remaining_clicks_in_charge: 0 });

  // Fetch grid data
  useEffect(() => {
    const fetchGrid = async () => {
      try {
        const response = await fetch("http://rbiz.pro/api/get-grid");
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

  useEffect(() => {
    
    // Listen for cell updates
    socket.on("cell-updated", (updatedCell) => {
      if (!updatedCell || !updatedCell.coordinates) {
        console.error("Invalid cell data received:", updatedCell);
        return;
      }
      setGrid((prevGrid) => ({
        ...prevGrid,
        [updatedCell.coordinates]: updatedCell,
      }));
    });
  
    // Listen for fort updates
    socket.on("fort-detected", (fortData) => {
      console.log("Fort detected:", fortData);
  
      // Update the grid with the fort's border and inner cells
      setGrid((prevGrid) => {
        const updatedGrid = { ...prevGrid };
  
        // Update border cells
        fortData.border_cells.forEach((coord) => {
          updatedGrid[coord] = {
            ...updatedGrid[coord],
            is_border: true,
            is_in_fort: true,
            fort_id: fortData.fort_id,
            level: fortData.level,
          };
        });
  
        // Update inner cells
        fortData.inner_cells.forEach((coord) => {
          updatedGrid[coord] = {
            ...updatedGrid[coord],
            is_inner: true,
            is_in_fort: true,
            fort_id: fortData.fort_id,
          };
        });
  
        return updatedGrid;
      });
    });
  
    return () => {
      socket.disconnect();
    };
  }, []);
  

  // Restore authentication state
  useEffect(() => {
    const restoreAuthState = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          console.error("No token found in localStorage");
          setUserId(null);
          setUsername("");
          return;
        }
        
        const response = await fetch("http://rbiz.pro/api/check-login", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
  
        console.log("Response status:", response.status);
  
        if (response.ok) {
          if (response.headers.get("Content-Type")?.includes("application/json")) {
            const data = await response.json();
            console.log("User data:", data);
            setUserId(data.userId);
            setUsername(data.username);
          } else {
            console.error("Non-JSON response received");
            setUserId(null);
            setUsername("");
          }
        } else {
          console.error("Failed to restore auth state. Status:", response.status);
          setUserId(null);
          setUsername("");
        }
      } catch (error) {
        console.error("Error restoring authentication state:", error);
        setUserId(null);
        setUsername("");
      } finally {
        setLoading(false);
      }
    };
  
    restoreAuthState();
  }, []);
  

  // Fetch energy details
  const fetchEnergy = async () => {
    try {
      const response = await fetch("http://rbiz.pro/api/get-energy", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({ userId }),
      });

      if (response.ok) {
        const data = await response.json();
        setEnergy(data.energy);
      } else {
        console.error("Error fetching energy data");
      }
    } catch (error) {
      console.error("Error fetching energy data:", error);
    }
  };

  const handleOpenLogoutModal = () => {
    fetchEnergy();
    setIsLogoutModalOpen(true);
  };

  // Request login code
  const requestLoginCode = async () => {
    setIsRequestingCode(true);
    try {
      const response = await fetch("http://rbiz.pro/api/request-login-code", {
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
      const response = await fetch("http://rbiz.pro/api/verify-login-code", {
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

  const handleCellClick = useCallback(
    async (row, col) => {
      if (!userId) {
        alert("You must be logged in to claim a cell.");
        return;
      }

      try {
        const response = await fetch("http://rbiz.pro/api/claim-cell", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
          body: JSON.stringify({ row, col, userId }),
        });
        const responseText = await response.text(); // Log the raw response
        console.log("Response text:", responseText);

        if (response.ok) {
          const updatedGrid = await fetch("http://rbiz.pro/api/get-grid");
          console.log("🚀 ~ updatedGrid:", updatedGrid)
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
  
    // Determine styles based on cell properties
    const cellStyles = {
      ...style,
      width: `${cellSize}px`,
      height: `${cellSize}px`,
      backgroundColor: cell.color || "transparent", // Apply the cell's color or transparent
      border: cell.is_border
        ? `2px solid ${cell.color || "black"}` // Border color matches the cell's color
        : "1px solid #ddd", // Default border
    };
  
    return (
      <div
        style={cellStyles}
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
        onClick={() => (username ? handleOpenLogoutModal() : setIsLoginModalOpen(true))}
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
            <p>Remaining Clicks in Current Charge: {energy.remaining_clicks_in_charge}</p>
            <p>Charges Remaining: {energy.charges}</p>
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
