import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import SelectionPage from "./pages/SelectionPage";
import SearchPage from "./pages/SearchPage";
import CollectionsPage from "./pages/CollectionsPage";
import AttributionPage from "./pages/AttributionPage";
import EvalsPage from "./pages/EvalsPage";

export default function App() {
  const [institutionId, setInstitutionId] = useState<string | null>(null);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            institutionId
              ? <Navigate to="/search" replace />
              : <SelectionPage onSelect={setInstitutionId} />
          }
        />
        <Route
          path="/search"
          element={
            institutionId
              ? <SearchPage institutionId={institutionId} onSwitch={() => setInstitutionId(null)} />
              : <Navigate to="/" replace />
          }
        />
        <Route
          path="/collections"
          element={
            institutionId
              ? <CollectionsPage institutionId={institutionId} onSwitch={() => setInstitutionId(null)} />
              : <Navigate to="/" replace />
          }
        />
        <Route
          path="/attribution"
          element={
            institutionId
              ? <AttributionPage onSwitch={() => setInstitutionId(null)} />
              : <Navigate to="/" replace />
          }
        />
        <Route path="/evals" element={<EvalsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
