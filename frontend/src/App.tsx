// no default React import needed with react-jsx
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import VectorStorePage from "./pages/VectorStorePage";
import SettingsPage from "./pages/SettingsPage";
import SystemStatusPage from "./pages/SystemStatusPage";
import UsageDashboard from "./pages/UsageDashboard";
import IngestPage from "./pages/IngestPage";
import FilesManagerPage from "./pages/FilesManagerPage";
import KnowledgeBasesPage from "./pages/KnowledgeBasesPage";
import KnowledgeBaseDetail from "./pages/KnowledgeBaseDetail";
import LoginPage from "./pages/LoginPage";
import AuthGuard from "./components/AuthGuard";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <AuthGuard>
              <Layout />
            </AuthGuard>
          }
        >
          <Route index element={<ChatPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="search" element={<VectorStorePage />} />
          <Route path="ingest" element={<IngestPage />} />
          <Route path="files" element={<FilesManagerPage />} />
          <Route path="kb" element={<KnowledgeBasesPage />} />
          <Route path="kb/:name" element={<KnowledgeBaseDetail />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="status" element={<SystemStatusPage />} />
          <Route path="usage" element={<UsageDashboard />} />
          <Route path="*" element={<ChatPage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
