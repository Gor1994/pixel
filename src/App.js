import React from "react";
import CellGrid from "./components/CellGrid";
import { AuthProvider } from "./contexts/AuthContext";

function App() {
  return (
    <AuthProvider>
      <CellGrid />
    </AuthProvider>
  );
}

export default App;
