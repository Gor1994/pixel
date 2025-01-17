import React, { useState, useEffect } from "react";

const GRID_SIZE = 20; // For simplicity, using 20x20 instead of 2000x2000

const Pixel = () => {
  const [grid, setGrid] = useState([]);
  const [energy, setEnergy] = useState(2000);

  useEffect(() => {
    // Initialize grid
    const initialGrid = Array(GRID_SIZE)
      .fill(null)
      .map(() =>
        Array(GRID_SIZE).fill({ owner: null, level: 0, timestamp: null })
      );
    setGrid(initialGrid);
  }, []);

  const handleClick = (x, y) => {
    if (energy <= 0) return;

    setGrid((prevGrid) => {
      const newGrid = [...prevGrid];
      const cell = newGrid[x][y];

      // Update cell ownership or level
      if (!cell.owner) {
        newGrid[x][y] = { owner: "player1", level: 1, timestamp: Date.now() };
      } else if (cell.owner === "player1") {
        newGrid[x][y] = {
          ...cell,
          level: cell.level + 1,
          timestamp: Date.now(),
        };
      }

      return newGrid;
    });

    setEnergy((prev) => prev - 1);
  };

  return (
    <div>
      <h1>Interactive Game</h1>
      <p>Energy: {energy}</p>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${GRID_SIZE}, 20px)` }}>
        {grid.flat().map((cell, index) => (
          <div
            key={index}
            onClick={() => handleClick(Math.floor(index / GRID_SIZE), index % GRID_SIZE)}
            style={{
              width: 20,
              height: 20,
              border: "1px solid black",
              backgroundColor: cell.owner ? "blue" : "white",
              textAlign: "center",
              lineHeight: "20px",
              fontSize: "12px",
            }}
          >
            {cell.level}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Pixel;
