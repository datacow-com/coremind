import {
	Activity,
	ClipboardList,
	Download,
	FileText,
	LayoutTemplate,
	Search,
	Settings,
	Upload,
	Zap, // Icon for Capability Config
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { z } from "zod";
import { KBCapabilityConfig } from "@/components/KBCapabilityConfig";
import { StrategyConfig } from "@/components/StrategyConfig";
import Button from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { SelectSearch } from "@/components/ui/select-search";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast-provider";
import { useDebouncedEffect } from "@/hooks/useDebouncedEffect";
import { useFormZod } from "@/hooks/useFormZod";
import { apiFetch } from "@/lib/api";

const fetch = apiFetch;

// ... (Existing Interfaces and Component Logic) ...

// In KnowledgeBaseDetail component, update the updateKb function to accept strategy config
// The existing updateKb just PATCHes payload. If backend accepts nested strategy_config, we are good.
// We need to ensure backend (server/routes.py update_kb) handles it.
// The legacy backend might store extra keys in config json blob.

const KnowledgeBaseDetail: React.FC = () => {
	// ... (Existing State) ...
	const { name } = useParams();
	const [tab, setTab] = useState<string>("strategy");
	const [runtime, setRuntime] = useState<any>({});
	const [kbConfig, setKbConfig] = useState<any>({});
	const [effectiveConfig, setEffectiveConfig] = useState<any>({});
	const [scenarios, setScenarios] = useState<Record<string, any>>({});
	const [selectedScenario, setSelectedScenario] = useState<string>("");
	const [retrievalForm, setRetrievalForm] = useState<any>({
		top_k_default: 5,
		candidate_k: 50,
		vector_weight: 0.6,
		keyword_weight: 0.4,
		rrf_k: 60,
		reranker_filter_threshold: 0.2,
		enable_rerank: false,
		rerank_model: "",
	});
	const [settingsForm, setSettingsForm] = useState<any>({
		description: "",
		stack: "cn",
		visibility: "private",
	});
	const { push } = useToast();

	// ... (Existing Load Logic) ...

	const load = async () => {
		try {
			const r = await fetch(
				`/api/kb/${encodeURIComponent(String(name || ""))}/config`,
			);
			if (r.ok) {
				const d = await r.json();
				setKbConfig(d.config || {});
				setEffectiveConfig(d.effective_config || {});
				setRetrievalForm({
					top_k_default: d.config?.top_k_default ?? 5,
					candidate_k: d.config?.candidate_k ?? 50,
					vector_weight: d.config?.vector_weight ?? 0.6,
					keyword_weight: d.config?.keyword_weight ?? 0.4,
					rrf_k: d.config?.rrf_k ?? 60,
					reranker_filter_threshold: d.config?.reranker_filter_threshold ?? 0.2,
					enable_rerank: d.config?.enable_rerank ?? false,
					rerank_model: d.config?.rerank_model || "",
				});
				setSettingsForm({
					description: d.config?.description || "",
					stack: d.config?.stack || "cn",
					visibility: d.config?.visibility || "private",
				});
				// ... populate forms ...
			}
		} catch {}
	};

	const loadScenarios = async () => {
		try {
			const r = await fetch(`/api/ingest/scenarios`);
			if (r.ok) {
				const d = await r.json();
				setScenarios(d.scenarios || {});
			}
		} catch {}
	};

	useEffect(() => {
		load();
		loadScenarios();
	}, [name]);

	const updateKb = async (payload: any) => {
		try {
			const r = await fetch(
				`/api/kb/${encodeURIComponent(String(name || ""))}/config`,
				{
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(payload),
				},
			);
			if (r.ok) {
				load(); // Reload to refresh effective config
			} else {
				push({ title: "更新失败", variant: "error" });
			}
		} catch {
			push({ title: "网络错误", variant: "error" });
		}
	};

	return (
		<div className="flex h-full flex-col bg-gray-50">
			{/* Header */}
			<div className="bg-white border-b px-6 py-4 flex justify-between items-center">
				<div>
					<h1 className="text-xl font-bold text-gray-800 flex items-center">
						{name}
						<span className="ml-3 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
							{effectiveConfig.stack === "en" ? "English" : "中文"}
						</span>
					</h1>
					<p className="text-sm text-gray-500 mt-1">
						{effectiveConfig.description || "暂无描述"}
					</p>
				</div>
				<div className="flex space-x-2">{/* ... Actions ... */}</div>
			</div>

			<div className="flex-1 overflow-hidden flex">
				{/* Sidebar */}
				<div className="w-64 bg-white border-r flex flex-col">
					<nav className="flex-1 p-4 space-y-1">
						<button
							onClick={() => setTab("files")}
							className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
								tab === "files"
									? "bg-blue-50 text-blue-700"
									: "text-gray-700 hover:bg-gray-100"
							}`}
						>
							<FileText className="h-5 w-5" />
							<span>文件管理</span>
						</button>
						<button
							onClick={() => setTab("capabilities")}
							className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
								tab === "capabilities"
									? "bg-blue-50 text-blue-700"
									: "text-gray-700 hover:bg-gray-100"
							}`}
						>
							<Zap className="h-5 w-5" />
							<span>能力配置</span>
						</button>
						<button
							onClick={() => setTab("strategy")}
							className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
								tab === "strategy"
									? "bg-blue-50 text-blue-700"
									: "text-gray-700 hover:bg-gray-100"
							}`}
						>
							<LayoutTemplate className="h-5 w-5" />
							<span>策略配置 (V4)</span>
						</button>
						<button
							onClick={() => setTab("retrieval")}
							className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
								tab === "retrieval"
									? "bg-blue-50 text-blue-700"
									: "text-gray-700 hover:bg-gray-100"
							}`}
						>
							<Search className="h-5 w-5" />
							<span>检索参数</span>
						</button>
						<button
							onClick={() => setTab("settings")}
							className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
								tab === "settings"
									? "bg-blue-50 text-blue-700"
									: "text-gray-700 hover:bg-gray-100"
							}`}
						>
							<Settings className="h-5 w-5" />
							<span>基础设置</span>
						</button>
					</nav>
				</div>

				{/* Content Area */}
				<div className="flex-1 overflow-auto p-8">
					{tab === "files" && (
						<div className="text-gray-500">文件列表组件 (Placeholder)</div>
						/* Reuse existing file list logic here */
					)}

					{tab === "capabilities" && name && (
						<div className="max-w-4xl mx-auto">
							<KBCapabilityConfig kbName={name} />
						</div>
					)}

					{tab === "strategy" && (
						<div className="max-w-4xl mx-auto">
							<Card>
								<CardHeader>
									<CardTitle>Ingestion Strategy (V4 Pipeline)</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="space-y-4">
										<div className="flex items-center gap-3">
											<label className="text-sm">场景预设</label>
											<select
												value={selectedScenario}
												onChange={(e) => setSelectedScenario(e.target.value)}
												className="border rounded p-2"
											>
												<option value="">不应用预设</option>
												{Object.keys(scenarios).map((k) => (
													<option key={k} value={k}>
														{k}
													</option>
												))}
											</select>
											<button
												className="px-3 py-1 border rounded text-sm"
												onClick={() => {
													if (selectedScenario && scenarios[selectedScenario]) {
														updateKb({
															strategy_config: scenarios[selectedScenario],
															scenario: selectedScenario,
														});
														setKbConfig((prev: any) => ({
															...prev,
															strategy_config: {
																...(prev?.strategy_config || {}),
																...scenarios[selectedScenario],
															},
														}));
													}
												}}
											>
												应用预设
											</button>
										</div>

										<StrategyConfig
											initialConfig={
												kbConfig.strategy_config ||
												effectiveConfig.strategy_config ||
												{}
											}
											onSubmit={(cfg: any) =>
												updateKb({ strategy_config: cfg })
											}
										/>
									</div>
								</CardContent>
							</Card>
						</div>
					)}

					{tab === "retrieval" && (
						<Card className="max-w-3xl">
							<CardHeader>
								<CardTitle>检索参数</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label>Top K</Label>
									<Input
										type="number"
										value={retrievalForm.top_k_default ?? 5}
										onChange={(e) =>
											setRetrievalForm({
												...retrievalForm,
												top_k_default: Number(e.target.value),
											})
										}
									/>
								</div>
								<div className="space-y-2">
									<Label>Rerank Model</Label>
									<Input
										placeholder="cross-encoder/bge-rerank"
										value={retrievalForm.rerank_model || ""}
										onChange={(e) =>
											setRetrievalForm({
												...retrievalForm,
												rerank_model: e.target.value,
											})
										}
									/>
								</div>
								<div className="grid grid-cols-2 gap-3">
									<div className="space-y-2">
										<Label>候选数</Label>
										<Input
											type="number"
											value={retrievalForm.candidate_k ?? 50}
											onChange={(e) =>
												setRetrievalForm({
													...retrievalForm,
													candidate_k: Number(e.target.value),
												})
											}
										/>
									</div>
									<div className="space-y-2">
										<Label>RRF K</Label>
										<Input
											type="number"
											value={retrievalForm.rrf_k ?? 60}
											onChange={(e) =>
												setRetrievalForm({
													...retrievalForm,
													rrf_k: Number(e.target.value),
												})
											}
										/>
									</div>
								</div>
								<div className="grid grid-cols-2 gap-3">
									<div className="space-y-2">
										<Label>向量权重</Label>
										<Input
											type="number"
											step="0.05"
											value={retrievalForm.vector_weight ?? 0.6}
											onChange={(e) =>
												setRetrievalForm({
													...retrievalForm,
													vector_weight: Number(e.target.value),
												})
											}
										/>
									</div>
									<div className="space-y-2">
										<Label>关键词权重</Label>
										<Input
											type="number"
											step="0.05"
											value={retrievalForm.keyword_weight ?? 0.4}
											onChange={(e) =>
												setRetrievalForm({
													...retrievalForm,
													keyword_weight: Number(e.target.value),
												})
											}
										/>
									</div>
								</div>
								<div className="space-y-2">
									<Label>Rerank 过滤阈值</Label>
									<Input
										type="number"
										step="0.01"
										value={retrievalForm.reranker_filter_threshold ?? 0.2}
										onChange={(e) =>
											setRetrievalForm({
												...retrievalForm,
												reranker_filter_threshold: Number(e.target.value),
											})
										}
									/>
								</div>
								<div className="flex items-center gap-2">
									<Switch
										checked={!!retrievalForm.enable_rerank}
										onChange={(e) =>
											setRetrievalForm({
												...retrievalForm,
												enable_rerank: e.target.checked,
											})
										}
									/>
									<span>启用 Rerank</span>
								</div>
								<div className="flex justify-end">
									<Button
										onClick={async () => {
											await updateKb({ ...retrievalForm });
											load();
										}}
									>
										保存检索参数
									</Button>
								</div>
							</CardContent>
						</Card>
					)}

					{tab === "settings" && (
						<Card className="max-w-3xl">
							<CardHeader>
								<CardTitle>基础设置</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label>描述</Label>
									<Input
										value={settingsForm.description || ""}
										onChange={(e) =>
											setSettingsForm({
												...settingsForm,
												description: e.target.value,
											})
										}
									/>
								</div>
								<div className="space-y-2">
									<Label>语言</Label>
									<Input
										value={settingsForm.stack || "cn"}
										onChange={(e) =>
											setSettingsForm({
												...settingsForm,
												stack: e.target.value,
											})
										}
									/>
								</div>
								<div className="space-y-2">
									<Label>可见性</Label>
									<select
										className="border rounded p-2"
										value={settingsForm.visibility || "private"}
										onChange={(e) =>
											setSettingsForm({
												...settingsForm,
												visibility: e.target.value,
											})
										}
									>
										<option value="private">Private</option>
										<option value="org">Org</option>
										<option value="public">Public</option>
									</select>
								</div>
								<div className="flex justify-end">
									<Button
										onClick={async () => {
											await updateKb({ ...settingsForm });
											load();
										}}
									>
										保存基础设置
									</Button>
								</div>
							</CardContent>
						</Card>
					)}
				</div>
			</div>
		</div>
	);
};

export default KnowledgeBaseDetail;
