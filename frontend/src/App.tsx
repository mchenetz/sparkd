import { Link, Route, Routes } from "react-router-dom";

import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <Link to="/">Boxes</Link>
        <Link to="/recipes">Recipes</Link>
        <Link to="/launch">Launch</Link>
        <Link to="/status">Status</Link>
      </nav>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
      </Routes>
    </div>
  );
}
