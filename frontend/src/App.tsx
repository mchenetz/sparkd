import { Link, Route, Routes } from "react-router-dom";

import AdvisorPage from "./pages/AdvisorPage";
import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import ModsPage from "./pages/ModsPage";
import OptimizePage from "./pages/OptimizePage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        <Link to="/">Boxes</Link>
        <Link to="/recipes">Recipes</Link>
        <Link to="/launch">Launch</Link>
        <Link to="/status">Status</Link>
        <Link to="/advisor">Advisor</Link>
        <Link to="/optimize">Optimize</Link>
        <Link to="/mods">Mods</Link>
      </nav>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/advisor" element={<AdvisorPage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="/mods" element={<ModsPage />} />
      </Routes>
    </div>
  );
}
