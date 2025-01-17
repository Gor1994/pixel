import React, { useState, useEffect } from "react";
import { FixedSizeGrid as Grid } from "react-window";
import "../styles/CellGrid.css";
import "../styles/Login.css";

const CellGrid = ({ gridSize = 2000, cellSize = 20 }) => {
  const [grid, setGrid] = useState({}); // Store only claimed cells
  const [userId, setUserId] = useState(null); // User ID (null initially for login)
  const [hoveredFortLevel, setHoveredFortLevel] = useState(null); // Store the level of the hovered fort
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 }); // Tooltip position
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false); // Modal visibility state
  const [username, setUsername] = useState(""); // Input value for username

  // Fetch grid state from backend on initial load
  useEffect(() => {
    const fetchGrid = async () => {
      try {
        const response = await fetch("http://127.0.0.1:5000/get-grid");
        const data = await response.json();

        // Convert array response to object for easier access
        const gridData = {};
        data.forEach((cell) => {
          gridData[cell.coordinates] = cell;
        });

        setGrid(gridData);
        console.log("Grid fetched:", gridData); // Debugging log
      } catch (error) {
        console.error("Error fetching grid:", error);
      }
    };

    fetchGrid();
  }, []);

  // Handle cell click
  const handleCellClick = async (row, col) => {
    try {
      const response = await fetch("http://127.0.0.1:5000/claim-cell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row, col, userId }),
      });

      if (response.ok) {
        // Fetch the latest grid after claiming a cell
        const updatedGrid = await fetch("http://127.0.0.1:5000/get-grid");
        const data = await updatedGrid.json();

        // Convert array response to object for easier access
        const gridData = {};
        data.forEach((cell) => {
          gridData[cell.coordinates] = cell;
        });

        setGrid(gridData); // Update the grid state
        console.log("Updated grid after claiming cell:", gridData); // Debugging log
      } else {
        const errorData = await response.json();
        console.error("Error claiming cell:", errorData.error);
      }
    } catch (error) {
      console.error("Error sending cell claim request:", error);
    }
  };

  // Handle hover to show fort level
  const handleMouseEnter = (event, cell) => {
    console.log("Hovered Cell:", cell); // Debug log
    if (cell.is_border && cell.fort_level !== undefined) {
      setHoveredFortLevel(cell.fort_level);
      setTooltipPosition({
        top: event.clientY + 10, // Offset tooltip from mouse position
        left: event.clientX + 10,
      });
      console.log("Tooltip shown at:", event.clientY, event.clientX); // Debug log
    }
  };

  const handleMouseLeave = () => {
    setHoveredFortLevel(null);
  };

  const handleLogin = () => {
    // Set the username as userId and close the modal
    setUserId(username || "Guest"); // Assign username or default to "Guest"
    setIsLoginModalOpen(false); // Close the modal
    console.log("User logged in:", username);
  };

  // Cell renderer for the virtualized grid
  const Cell = ({ columnIndex, rowIndex, style }) => {
    const cellKey = `${rowIndex}-${columnIndex}`;
    const cell = grid[cellKey] || {}; // Get the cell state from the grid

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
        onClick={() => {
          if (!cell.user_id || cell.user_id === userId) {
            handleCellClick(rowIndex, columnIndex);
          }
        }}
        onMouseEnter={(event) => handleMouseEnter(event, cell)}
        onMouseLeave={handleMouseLeave}
      >
        {cell.level !== undefined && (
          <div className="cell-level">{cell.level}</div>
        )}
      </div>
    );
  };

  return (
    <div className="grid-scrollable">
      {/* Login Button */}
      <button
        className="login-button"
        onClick={() => setIsLoginModalOpen(true)}
      >
        {userId ? `Logged in as: ${userId}` : "Login"}
      </button>

      {/* Login Modal */}
      {isLoginModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Login</h2>
            <input
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <button onClick={handleLogin}>Login</button>
            <button onClick={() => setIsLoginModalOpen(false)}>Cancel</button>
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
        height={window.innerHeight} // Viewport height
        width={window.innerWidth} // Viewport width
        itemData={grid} // Pass grid as itemData
      >
        {Cell}
      </Grid>
    </div>
  );
};

export default CellGrid;
