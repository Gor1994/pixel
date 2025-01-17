import React, { useState, useEffect } from "react";
import axios from "axios";
import { CELL_SIZE } from "../constants/game";
import "../styles/Gameboard.css";

const GRID_SIZE = 100;

const GameBoard = () => {
  const [grid, setGrid] = useState([]);
  const [forts, setForts] = useState([]);
  const [userId] = useState("player1"); // Current player ID

  useEffect(() => {
    // Initialize grid
    setGrid(
      Array.from({ length: GRID_SIZE }, (_, y) =>
        Array.from({ length: GRID_SIZE }, (_, x) => ({
          id: `${x}-${y}`,
          x,
          y,
          owner: null,
          level: 0,
        }))
      )
    );
  }, []);

  const handleCellClick = async (x, y) => {
    try {
      const response = await axios.post("http://localhost:5000/click", {
        x,
        y,
        user_id: userId,
      });
  
      const { board, forts: detectedForts } = response.data || {};
  
      if (!board || !detectedForts) {
        console.error("Unexpected response format:", response.data);
        return;
      }
  
      // Update grid state
      setGrid(
        board.map((row, y) =>
          row.map((cell, x) => ({
            id: `${x}-${y}`,
            x,
            y,
            owner: cell.owner,
            level: cell.level,
          }))
        )
      );
  
      // Update forts with boundary and inner cells
      setForts(
        detectedForts.map((fort) => ({
          boundary_cells: fort.boundary_cells,
          inner_cells: fort.inner_cells,
        }))
      );
    } catch (error) {
      console.error("Error clicking cell:", error.response?.data?.error || error.message);
    }
  };
  
  

  const getCellClass = (cell) => {
    // Check if the cell is part of a fort
    const isBoundary = forts.some((fort) =>
      fort.boundary_cells.some(([fx, fy]) => fx === cell.x && fy === cell.y)
    );
  
    const isInnerCell = forts.some((fort) =>
      fort.inner_cells.some(([fx, fy]) => fx === cell.x && fy === cell.y)
    );
  
    if (isBoundary) return "cell-fort-boundary";
    if (isInnerCell) return "cell-fort-inner";
  
    // Handle other cases
    if (!cell.owner) return "cell-empty";
    if (cell.owner === userId) return "cell-user-owned";
  
    // Assign colors for other players dynamically
    const playerColors = {
      player2: "cell-player-2",
      player3: "cell-player-3",
      player4: "cell-player-4",
    };
  
    return playerColors[cell.owner] || "cell-other-owned";
  };
  

  return (
    <div className="gameboard-container">
      <h1 className="gameboard-header">Multiplayer Game Board</h1>
      <div className="gameboard-grid" style={{ gridTemplateColumns: `repeat(${GRID_SIZE}, ${CELL_SIZE}px)` }}>
        {grid.map((row, rowIndex) =>
          row.map((cell, cellIndex) => (
            <div
              key={`${rowIndex}-${cellIndex}`}
              onClick={() => handleCellClick(cell.x, cell.y)}
              className={`gameboard-cell ${getCellClass(cell)}`}
            ></div>
          ))
        )}
      </div>
    </div>
  );
};

export default GameBoard;
