import { Route, Routes } from "react-router-dom";

import Shell from "./components/Shell";
import AdvisorPage from "./pages/AdvisorPage";
import BoxesPage from "./pages/BoxesPage";
import LaunchPage from "./pages/LaunchPage";
import ModDetailPage from "./pages/ModDetailPage";
import ModsPage from "./pages/ModsPage";
import OptimizePage from "./pages/OptimizePage";
import RecipeDetailPage from "./pages/RecipeDetailPage";
import RecipesPage from "./pages/RecipesPage";
import StatusPage from "./pages/StatusPage";

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<BoxesPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/recipes/:name" element={<RecipeDetailPage />} />
        <Route path="/launch" element={<LaunchPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/advisor" element={<AdvisorPage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="/mods" element={<ModsPage />} />
        <Route path="/mods/:name" element={<ModDetailPage />} />
      </Routes>
    </Shell>
  );
}
