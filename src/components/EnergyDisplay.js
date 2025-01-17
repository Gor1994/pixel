import React from "react";

function EnergyDisplay({ energy }) {
  return (
    <div style={{ color: "white", padding: "10px" }}>
      <p>Charges: {energy.charges}</p>
      <p>Clicks: {energy.clicks}</p>
    </div>
  );
}

export default EnergyDisplay;
