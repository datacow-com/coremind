import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Home from "@/pages/Home";
import Providers from "@/pages/Providers";
import Dashboard from "@/pages/Dashboard";
import AuditLogs from "@/pages/AuditLogs";
import TaskBindings from "@/pages/TaskBindings";
import Credentials from "@/pages/Credentials";
import Environments from "@/pages/Environments";

export default function App() {
  return (
    <Router>
      <div className="flex flex-col min-h-screen">
        <div className="border-b p-3 flex gap-4">
          <a href="/" className="font-semibold">OmniRAG</a>
          <a href="/providers" className="underline">Providers</a>
          <a href="/bindings" className="underline">Bindings</a>
          <a href="/credentials" className="underline">Credentials</a>
          <a href="/environments" className="underline">Environments</a>
          <a href="/dashboard" className="underline">Dashboard</a>
          <a href="/audit" className="underline">Audit</a>
        </div>
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/providers" element={<Providers />} />
            <Route path="/bindings" element={<TaskBindings />} />
            <Route path="/credentials" element={<Credentials />} />
            <Route path="/environments" element={<Environments />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/audit" element={<AuditLogs />} />
            <Route path="/other" element={<div className="text-center text-xl">Other Page - Coming Soon</div>} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}
