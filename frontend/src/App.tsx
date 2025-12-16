// no default React import needed with react-jsx
import { Route, HashRouter as Router, Routes } from "react-router-dom";
import AuthGuard from "./components/AuthGuard";
import Layout from "./components/Layout";
import AlgorithmConsolePage from "./pages/AlgorithmConsolePage";
import CapabilityStorePage from "./pages/CapabilityStorePage";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import DomainManagerPage from "./pages/DomainManagerPage";
import FilesManagerPage from "./pages/FilesManagerPage";
import IngestPage from "./pages/IngestPage";
import KnowledgeBaseDetail from "./pages/KnowledgeBaseDetail";
import KnowledgeBasesPage from "./pages/KnowledgeBasesPage";
import LLMStrategyPage from "./pages/LLMStrategyPage";
import LoginPage from "./pages/LoginPage";
import SettingsPage from "./pages/SettingsPage";
import SystemStatusPage from "./pages/SystemStatusPage";
import UsageDashboard from "./pages/UsageDashboard";
import VectorStorePage from "./pages/VectorStorePage";

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
					<Route path="capabilities" element={<CapabilityStorePage />} />
					<Route path="algorithms" element={<AlgorithmConsolePage />} />
					<Route path="domains" element={<DomainManagerPage />} />
					<Route path="llm-strategy" element={<LLMStrategyPage />} />
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
