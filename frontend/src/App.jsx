import { Routes, Route } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentDetailsPage } from "./pages/DocumentDetailsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { EvidencePage } from "./pages/EvidencePage";
import { GraphPage } from "./pages/GraphPage";
import { QueryPage } from "./pages/QueryPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailsPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
