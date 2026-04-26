import { Route, Routes } from "react-router-dom";

import Shell from "./components/Shell";
import AdvisorPage from "./pages/AdvisorPage";
import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import ModsPage from "./pages/ModsPage";
import OptimizePage from "./pages/OptimizePage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/advisor" element={<AdvisorPage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="/mods" element={<ModsPage />} />
      </Routes>
    </Shell>
  );
}
