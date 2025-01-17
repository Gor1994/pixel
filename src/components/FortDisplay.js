import React from "react";

function FortDisplay({ forts }) {
  return (
    <div style={{ color: "white", padding: "10px" }}>
      <h3>Forts</h3>
      <ul>
        {forts.map((fort) => (
          <li key={fort.id}>
            Fort ID: {fort.id}, Level: {fort.level}, Cells: {fort.cells.length}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default FortDisplay;
