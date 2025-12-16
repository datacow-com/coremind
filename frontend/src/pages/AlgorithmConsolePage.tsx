/**
 * AlgorithmConsolePage - 算法控制台页面
 *
 * 展示 RAPTOR、GraphRAG、MindMap 算法的配置面板，支持执行和监控
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
 */

import {
	Brain,
	Clock,
	DollarSign,
	GitBranch,
	Network,
	Play,
	TreePine,
} from "lucide-react";
import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
	type AlgorithmMode,
	type AlgorithmProgress,
	type AlgorithmTask,
	type AlgorithmType,
	useCapabilityStore,
} from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

interface KBInfo {
	name: string;
	chunk_count: number;
	embedding_dimension: number;
}

interface RaptorConfig {
	mode: AlgorithmMode;
	max_clusters: number;
	levels: number;
	summary_max_tokens: number;
}

interface GraphRAGConfig {
	entity_types: string[];
	community_algorithm: string;
	max_community_size: number;
	enable_global_search: boolean;
}

interface MindMapConfig {
	mode: AlgorithmMode;
	max_depth: number;
	branch_factor: number;
	include_summaries: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════════

const ALGORITHM_TABS = [
	{
		id: "raptor" as AlgorithmType,
		name: "RAPTOR",
		icon: TreePine,
		description: "递归摘要聚类算法",
	},
	{
		id: "graphrag" as AlgorithmType,
		name: "GraphRAG",
		icon: Network,
		description: "知识图谱构建算法",
	},
	{
		id: "mindmap" as AlgorithmType,
		name: "MindMap",
		icon: Brain,
		description: "思维导图生成算法",
	},
];

const DEFAULT_RAPTOR_CONFIG: RaptorConfig = {
	mode: "light",
	max_clusters: 10,
	levels: 3,
	summary_max_tokens: 500,
};

const DEFAULT_GRAPHRAG_CONFIG: GraphRAGConfig = {
	entity_types: ["person", "organization", "location", "concept"],
	community_algorithm: "louvain",
	max_community_size: 50,
	enable_global_search: true,
};

const DEFAULT_MINDMAP_CONFIG: MindMapConfig = {
	mode: "light",
	max_depth: 4,
	branch_factor: 5,
	include_summaries: true,
};

const ENTITY_TYPE_OPTIONS = [
	{ value: "person", label: "人物" },
	{ value: "organization", label: "组织" },
	{ value: "location", label: "地点" },
	{ value: "concept", label: "概念" },
	{ value: "event", label: "事件" },
	{ value: "product", label: "产品" },
	{ value: "technology", label: "技术" },
];

const COMMUNITY_ALGORITHM_OPTIONS = [
	{ value: "louvain", label: "Louvain" },
	{ value: "leiden", label: "Leiden" },
	{ value: "label_propagation", label: "标签传播" },
];

// ═══════════════════════════════════════════════════════════════════════════════
// Cost Estimation
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Estimate cost based on KB size and algorithm configuration
 */
function estimateCost(
	algorithm: AlgorithmType,
	kbChunkCount: number,
	config: RaptorConfig | GraphRAGConfig | MindMapConfig,
): number {
	const baseTokensPerChunk = 500;
	const totalTokens = kbChunkCount * baseTokensPerChunk;

	// Cost per 1K tokens (approximate)
	const costPer1KTokens = 0.002;

	let multiplier = 1;

	switch (algorithm) {
		case "raptor": {
			const raptorConfig = config as RaptorConfig;
			// More levels = more summarization passes
			multiplier = raptorConfig.mode === "deep" ? 2.5 : 1.5;
			multiplier *= 1 + (raptorConfig.levels - 1) * 0.3;
			break;
		}
		case "graphrag": {
			const graphConfig = config as GraphRAGConfig;
			// More entity types = more extraction work
			multiplier = 2.0;
			multiplier *= 1 + graphConfig.entity_types.length * 0.1;
			if (graphConfig.enable_global_search) multiplier *= 1.2;
			break;
		}
		case "mindmap": {
			const mindmapConfig = config as MindMapConfig;
			multiplier = mindmapConfig.mode === "deep" ? 1.8 : 1.2;
			multiplier *= 1 + (mindmapConfig.max_depth - 2) * 0.15;
			break;
		}
	}

	const estimatedCost = (totalTokens / 1000) * costPer1KTokens * multiplier;
	return Math.round(estimatedCost * 100) / 100;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sub-Components
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * KB Selector Component
 */
const KBSelector: React.FC<{
	value: string;
	onChange: (value: string) => void;
	kbs: KBInfo[];
	disabled?: boolean;
}> = ({ value, onChange, kbs, disabled }) => {
	return (
		<div className="space-y-2">
			<label className="text-sm font-medium text-gray-700">目标知识库</label>
			<select
				value={value}
				onChange={(e) => onChange(e.target.value)}
				disabled={disabled}
				className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
				data-testid="kb-selector"
			>
				<option value="">选择知识库...</option>
				{kbs.map((kb) => (
					<option key={kb.name} value={kb.name}>
						{kb.name} ({kb.chunk_count} chunks)
					</option>
				))}
			</select>
		</div>
	);
};

/**
 * Mode Selector Component
 */
const ModeSelector: React.FC<{
	value: AlgorithmMode;
	onChange: (value: AlgorithmMode) => void;
	disabled?: boolean;
}> = ({ value, onChange, disabled }) => {
	return (
		<div className="space-y-2">
			<label className="text-sm font-medium text-gray-700">执行模式</label>
			<div className="flex space-x-2">
				<button
					type="button"
					onClick={() => onChange("light")}
					disabled={disabled}
					className={cn(
						"flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors",
						value === "light"
							? "bg-blue-600 text-white"
							: "bg-gray-100 text-gray-700 hover:bg-gray-200",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid="mode-light"
				>
					Light 模式
				</button>
				<button
					type="button"
					onClick={() => onChange("deep")}
					disabled={disabled}
					className={cn(
						"flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors",
						value === "deep"
							? "bg-blue-600 text-white"
							: "bg-gray-100 text-gray-700 hover:bg-gray-200",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid="mode-deep"
				>
					Deep 模式
				</button>
			</div>
			<p className="text-xs text-gray-500">
				{value === "light"
					? "快速处理，适合小型知识库"
					: "深度处理，生成更丰富的结构"}
			</p>
		</div>
	);
};

/**
 * Cost Estimator Display Component
 */
const CostEstimator: React.FC<{
	algorithm: AlgorithmType;
	kbChunkCount: number;
	config: RaptorConfig | GraphRAGConfig | MindMapConfig;
}> = ({ algorithm, kbChunkCount, config }) => {
	const estimatedCost = React.useMemo(
		() => estimateCost(algorithm, kbChunkCount, config),
		[algorithm, kbChunkCount, config],
	);

	return (
		<div
			className="flex items-center justify-between p-3 bg-amber-50 border border-amber-200 rounded-md"
			data-testid="cost-estimator"
		>
			<div className="flex items-center space-x-2">
				<DollarSign className="h-4 w-4 text-amber-600" />
				<span className="text-sm text-amber-800">预估成本</span>
			</div>
			<span className="text-sm font-medium text-amber-900">
				${estimatedCost.toFixed(2)}
			</span>
		</div>
	);
};

/**
 * Progress Bar Component
 */
const AlgorithmProgressBar: React.FC<{
	progress: AlgorithmProgress | null;
	task: AlgorithmTask | null;
}> = ({ progress, task }) => {
	const [elapsedTime, setElapsedTime] = React.useState(0);

	React.useEffect(() => {
		if (!task || task.status !== "running") {
			setElapsedTime(0);
			return;
		}

		const startTime = task.started_at
			? new Date(task.started_at).getTime()
			: Date.now();
		const interval = setInterval(() => {
			setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
		}, 1000);

		return () => clearInterval(interval);
	}, [task]);

	if (!task) return null;

	const formatTime = (seconds: number) => {
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${secs.toString().padStart(2, "0")}`;
	};

	const progressValue = progress?.progress ?? task.progress ?? 0;
	const stage = progress?.stage ?? task.stage ?? "";
	const message = progress?.message ?? "";

	return (
		<div className="space-y-3" data-testid="algorithm-progress">
			<div className="flex items-center justify-between text-sm">
				<div className="flex items-center space-x-2">
					<span className="font-medium text-gray-700">
						{stage || "准备中..."}
					</span>
					{task.status === "running" && (
						<span className="text-gray-500">({progressValue}%)</span>
					)}
				</div>
				<div className="flex items-center space-x-1 text-gray-500">
					<Clock className="h-4 w-4" />
					<span>{formatTime(elapsedTime)}</span>
				</div>
			</div>

			<div className="w-full bg-gray-200 rounded-full h-2">
				<div
					className={cn(
						"h-2 rounded-full transition-all duration-300",
						task.status === "completed"
							? "bg-green-500"
							: task.status === "failed"
								? "bg-red-500"
								: "bg-blue-600",
					)}
					style={{ width: `${progressValue}%` }}
				/>
			</div>

			{message && <p className="text-xs text-gray-500">{message}</p>}

			{task.status === "completed" && (
				<div className="flex items-center space-x-2 text-green-600 text-sm">
					<span>✓ 执行完成</span>
					{task.actual_cost && (
						<span className="text-gray-500">
							(实际成本: ${task.actual_cost.toFixed(2)})
						</span>
					)}
				</div>
			)}

			{task.status === "failed" && task.error && (
				<div className="text-red-600 text-sm bg-red-50 p-2 rounded">
					错误: {task.error}
				</div>
			)}
		</div>
	);
};

/**
 * Run History Table Component
 */
const RunHistoryTable: React.FC<{
	tasks: AlgorithmTask[];
	loading: boolean;
}> = ({ tasks, loading }) => {
	if (loading) {
		return <div className="text-center py-4 text-gray-500">加载中...</div>;
	}

	if (tasks.length === 0) {
		return (
			<div className="text-center py-8 text-gray-500">暂无执行历史记录</div>
		);
	}

	const formatDuration = (task: AlgorithmTask) => {
		if (!task.started_at || !task.completed_at) return "-";
		const start = new Date(task.started_at).getTime();
		const end = new Date(task.completed_at).getTime();
		const seconds = Math.floor((end - start) / 1000);
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${secs.toString().padStart(2, "0")}`;
	};

	const getStatusBadge = (status: string) => {
		const styles: Record<string, string> = {
			completed: "bg-green-100 text-green-800",
			failed: "bg-red-100 text-red-800",
			running: "bg-blue-100 text-blue-800",
			pending: "bg-gray-100 text-gray-800",
		};
		const labels: Record<string, string> = {
			completed: "完成",
			failed: "失败",
			running: "运行中",
			pending: "等待中",
		};
		return (
			<span
				className={cn(
					"px-2 py-0.5 rounded-full text-xs font-medium",
					styles[status] || styles.pending,
				)}
			>
				{labels[status] || status}
			</span>
		);
	};

	return (
		<div className="overflow-x-auto" data-testid="run-history-table">
			<table className="w-full text-sm">
				<thead>
					<tr className="border-b text-left text-gray-600">
						<th className="pb-2 font-medium">算法</th>
						<th className="pb-2 font-medium">知识库</th>
						<th className="pb-2 font-medium">状态</th>
						<th className="pb-2 font-medium">耗时</th>
						<th className="pb-2 font-medium">成本</th>
						<th className="pb-2 font-medium">时间</th>
					</tr>
				</thead>
				<tbody>
					{tasks.map((task) => (
						<tr key={task.task_id} className="border-b hover:bg-gray-50">
							<td className="py-2">
								<span className="font-medium">
									{task.algorithm.toUpperCase()}
								</span>
								<span className="text-gray-500 ml-1">({task.mode})</span>
							</td>
							<td className="py-2">{task.kb_name}</td>
							<td className="py-2">{getStatusBadge(task.status)}</td>
							<td className="py-2">{formatDuration(task)}</td>
							<td className="py-2">
								{task.actual_cost ? `$${task.actual_cost.toFixed(2)}` : "-"}
							</td>
							<td className="py-2 text-gray-500">
								{new Date(task.created_at).toLocaleString()}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// RAPTOR Config Panel
// ═══════════════════════════════════════════════════════════════════════════════

const RaptorConfigPanel: React.FC<{
	config: RaptorConfig;
	onChange: (config: RaptorConfig) => void;
	disabled?: boolean;
}> = ({ config, onChange, disabled }) => {
	return (
		<div className="space-y-4" data-testid="raptor-config-panel">
			<ModeSelector
				value={config.mode}
				onChange={(mode) => onChange({ ...config, mode })}
				disabled={disabled}
			/>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					最大聚类数 (max_clusters)
				</label>
				<input
					type="range"
					min={2}
					max={50}
					value={config.max_clusters}
					onChange={(e) =>
						onChange({ ...config, max_clusters: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="raptor-max-clusters"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>2</span>
					<span className="font-medium text-gray-700">
						{config.max_clusters}
					</span>
					<span>50</span>
				</div>
			</div>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					层级数 (levels)
				</label>
				<input
					type="range"
					min={1}
					max={5}
					value={config.levels}
					onChange={(e) =>
						onChange({ ...config, levels: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="raptor-levels"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>1</span>
					<span className="font-medium text-gray-700">{config.levels}</span>
					<span>5</span>
				</div>
			</div>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					摘要最大 Token 数 (summary_max_tokens)
				</label>
				<input
					type="range"
					min={100}
					max={2000}
					step={100}
					value={config.summary_max_tokens}
					onChange={(e) =>
						onChange({ ...config, summary_max_tokens: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="raptor-summary-tokens"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>100</span>
					<span className="font-medium text-gray-700">
						{config.summary_max_tokens}
					</span>
					<span>2000</span>
				</div>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// GraphRAG Config Panel
// ═══════════════════════════════════════════════════════════════════════════════

const GraphRAGConfigPanel: React.FC<{
	config: GraphRAGConfig;
	onChange: (config: GraphRAGConfig) => void;
	disabled?: boolean;
}> = ({ config, onChange, disabled }) => {
	const handleEntityTypeToggle = (entityType: string) => {
		const newTypes = config.entity_types.includes(entityType)
			? config.entity_types.filter((t) => t !== entityType)
			: [...config.entity_types, entityType];
		onChange({ ...config, entity_types: newTypes });
	};

	return (
		<div className="space-y-4" data-testid="graphrag-config-panel">
			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">实体类型</label>
				<div className="flex flex-wrap gap-2">
					{ENTITY_TYPE_OPTIONS.map((option) => (
						<button
							key={option.value}
							type="button"
							onClick={() => handleEntityTypeToggle(option.value)}
							disabled={disabled}
							className={cn(
								"px-3 py-1.5 rounded-full text-sm transition-colors",
								config.entity_types.includes(option.value)
									? "bg-blue-600 text-white"
									: "bg-gray-100 text-gray-700 hover:bg-gray-200",
								disabled && "opacity-50 cursor-not-allowed",
							)}
							data-testid={`entity-type-${option.value}`}
						>
							{option.label}
						</button>
					))}
				</div>
			</div>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					社区检测算法
				</label>
				<select
					value={config.community_algorithm}
					onChange={(e) =>
						onChange({ ...config, community_algorithm: e.target.value })
					}
					disabled={disabled}
					className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
					data-testid="graphrag-community-algorithm"
				>
					{COMMUNITY_ALGORITHM_OPTIONS.map((option) => (
						<option key={option.value} value={option.value}>
							{option.label}
						</option>
					))}
				</select>
			</div>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					最大社区大小 (max_community_size)
				</label>
				<input
					type="range"
					min={10}
					max={200}
					step={10}
					value={config.max_community_size}
					onChange={(e) =>
						onChange({ ...config, max_community_size: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="graphrag-max-community-size"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>10</span>
					<span className="font-medium text-gray-700">
						{config.max_community_size}
					</span>
					<span>200</span>
				</div>
			</div>

			<div className="flex items-center justify-between">
				<label className="text-sm font-medium text-gray-700">
					启用全局搜索
				</label>
				<button
					type="button"
					onClick={() =>
						onChange({
							...config,
							enable_global_search: !config.enable_global_search,
						})
					}
					disabled={disabled}
					className={cn(
						"relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
						config.enable_global_search ? "bg-blue-600" : "bg-gray-200",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid="graphrag-global-search"
				>
					<span
						className={cn(
							"inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
							config.enable_global_search ? "translate-x-6" : "translate-x-1",
						)}
					/>
				</button>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// MindMap Config Panel
// ═══════════════════════════════════════════════════════════════════════════════

const MindMapConfigPanel: React.FC<{
	config: MindMapConfig;
	onChange: (config: MindMapConfig) => void;
	disabled?: boolean;
}> = ({ config, onChange, disabled }) => {
	return (
		<div className="space-y-4" data-testid="mindmap-config-panel">
			<ModeSelector
				value={config.mode}
				onChange={(mode) => onChange({ ...config, mode })}
				disabled={disabled}
			/>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					最大深度 (max_depth)
				</label>
				<input
					type="range"
					min={2}
					max={8}
					value={config.max_depth}
					onChange={(e) =>
						onChange({ ...config, max_depth: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="mindmap-max-depth"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>2</span>
					<span className="font-medium text-gray-700">{config.max_depth}</span>
					<span>8</span>
				</div>
			</div>

			<div className="space-y-2">
				<label className="text-sm font-medium text-gray-700">
					分支因子 (branch_factor)
				</label>
				<input
					type="range"
					min={2}
					max={10}
					value={config.branch_factor}
					onChange={(e) =>
						onChange({ ...config, branch_factor: Number(e.target.value) })
					}
					disabled={disabled}
					className="w-full"
					data-testid="mindmap-branch-factor"
				/>
				<div className="flex justify-between text-xs text-gray-500">
					<span>2</span>
					<span className="font-medium text-gray-700">
						{config.branch_factor}
					</span>
					<span>10</span>
				</div>
			</div>

			<div className="flex items-center justify-between">
				<label className="text-sm font-medium text-gray-700">包含摘要</label>
				<button
					type="button"
					onClick={() =>
						onChange({
							...config,
							include_summaries: !config.include_summaries,
						})
					}
					disabled={disabled}
					className={cn(
						"relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
						config.include_summaries ? "bg-blue-600" : "bg-gray-200",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid="mindmap-include-summaries"
				>
					<span
						className={cn(
							"inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
							config.include_summaries ? "translate-x-6" : "translate-x-1",
						)}
					/>
				</button>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

const AlgorithmConsolePage: React.FC = () => {
	// State
	const [activeAlgorithm, setActiveAlgorithm] =
		React.useState<AlgorithmType>("raptor");
	const [selectedKB, setSelectedKB] = React.useState("");
	const [kbs, setKbs] = React.useState<KBInfo[]>([]);
	const [kbsLoading, setKbsLoading] = React.useState(false);

	// Algorithm configs
	const [raptorConfig, setRaptorConfig] = React.useState<RaptorConfig>(
		DEFAULT_RAPTOR_CONFIG,
	);
	const [graphragConfig, setGraphragConfig] = React.useState<GraphRAGConfig>(
		DEFAULT_GRAPHRAG_CONFIG,
	);
	const [mindmapConfig, setMindmapConfig] = React.useState<MindMapConfig>(
		DEFAULT_MINDMAP_CONFIG,
	);

	// Execution state
	const [currentTaskId, setCurrentTaskId] = React.useState<string | null>(null);
	const [currentTask, setCurrentTask] = React.useState<AlgorithmTask | null>(
		null,
	);
	const [progress, setProgress] = React.useState<AlgorithmProgress | null>(
		null,
	);
	const [isRunning, setIsRunning] = React.useState(false);

	// History state
	const [historyTasks, setHistoryTasks] = React.useState<AlgorithmTask[]>([]);
	const [historyLoading, setHistoryLoading] = React.useState(false);

	// Store
	const { runAlgorithm, subscribeToProgress, fetchAlgorithmHistory } =
		useCapabilityStore();

	// Load KBs on mount
	React.useEffect(() => {
		const loadKBs = async () => {
			setKbsLoading(true);
			try {
				const result = await apiJson<{
					kbs: Array<{
						name: string;
						stats?: { chunk_count?: number; embedding_dimension?: number };
					}>;
				}>("/api/kb");
				if (result.ok && result.data) {
					const kbList: KBInfo[] = result.data.kbs.map((kb) => ({
						name: kb.name,
						chunk_count: kb.stats?.chunk_count || 0,
						embedding_dimension: kb.stats?.embedding_dimension || 256,
					}));
					setKbs(kbList);
				}
			} catch (err) {
				console.error("Failed to load KBs:", err);
			} finally {
				setKbsLoading(false);
			}
		};
		loadKBs();
	}, []);

	// Load history on mount and when algorithm changes
	React.useEffect(() => {
		const loadHistory = async () => {
			setHistoryLoading(true);
			try {
				const result = await fetchAlgorithmHistory({
					algorithm: activeAlgorithm,
					page_size: 10,
				});
				setHistoryTasks(result.tasks);
			} catch (err) {
				console.error("Failed to load history:", err);
			} finally {
				setHistoryLoading(false);
			}
		};
		loadHistory();
	}, [activeAlgorithm, fetchAlgorithmHistory]);

	// Get current config based on active algorithm
	const getCurrentConfig = ():
		| RaptorConfig
		| GraphRAGConfig
		| MindMapConfig => {
		switch (activeAlgorithm) {
			case "raptor":
				return raptorConfig;
			case "graphrag":
				return graphragConfig;
			case "mindmap":
				return mindmapConfig;
		}
	};

	// Get current mode
	const getCurrentMode = (): AlgorithmMode => {
		switch (activeAlgorithm) {
			case "raptor":
				return raptorConfig.mode;
			case "graphrag":
				return "deep"; // GraphRAG doesn't have mode, default to deep
			case "mindmap":
				return mindmapConfig.mode;
		}
	};

	// Get selected KB info
	const selectedKBInfo = kbs.find((kb) => kb.name === selectedKB);

	// Handle run algorithm
	const handleRun = async () => {
		if (!selectedKB) return;

		setIsRunning(true);
		setProgress(null);
		setCurrentTask(null);

		try {
			const config = getCurrentConfig();
			const mode = getCurrentMode();
			const taskId = await runAlgorithm(
				activeAlgorithm,
				selectedKB,
				mode,
				config as unknown as Record<string, unknown>,
			);

			if (taskId) {
				setCurrentTaskId(taskId);

				// Subscribe to progress
				const unsubscribe = subscribeToProgress(
					taskId,
					(prog) => {
						setProgress(prog);
					},
					(task) => {
						setCurrentTask(task);
						setIsRunning(false);
						// Refresh history
						fetchAlgorithmHistory({
							algorithm: activeAlgorithm,
							page_size: 10,
						}).then((result) => setHistoryTasks(result.tasks));
					},
					(error) => {
						console.error("Task error:", error);
						setIsRunning(false);
					},
				);

				// Store unsubscribe for cleanup
				return () => unsubscribe();
			} else {
				setIsRunning(false);
			}
		} catch (err) {
			console.error("Failed to run algorithm:", err);
			setIsRunning(false);
		}
	};

	// Render config panel based on active algorithm
	const renderConfigPanel = () => {
		switch (activeAlgorithm) {
			case "raptor":
				return (
					<RaptorConfigPanel
						config={raptorConfig}
						onChange={setRaptorConfig}
						disabled={isRunning}
					/>
				);
			case "graphrag":
				return (
					<GraphRAGConfigPanel
						config={graphragConfig}
						onChange={setGraphragConfig}
						disabled={isRunning}
					/>
				);
			case "mindmap":
				return (
					<MindMapConfigPanel
						config={mindmapConfig}
						onChange={setMindmapConfig}
						disabled={isRunning}
					/>
				);
		}
	};

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="bg-white border-b px-6 py-4">
				<div className="flex items-center space-x-2">
					<GitBranch className="h-5 w-5 text-blue-600" />
					<h2 className="text-lg font-semibold text-gray-800">算法控制台</h2>
				</div>
				<p className="text-sm text-gray-500 mt-1">
					执行高级算法构建增强知识结构
				</p>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-auto p-6">
				<div className="max-w-4xl mx-auto space-y-6">
					{/* Algorithm Tabs */}
					<div className="flex space-x-2 border-b">
						{ALGORITHM_TABS.map((tab) => {
							const Icon = tab.icon;
							const isActive = activeAlgorithm === tab.id;
							return (
								<button
									type="button"
									key={tab.id}
									onClick={() => setActiveAlgorithm(tab.id)}
									disabled={isRunning}
									className={cn(
										"flex items-center space-x-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
										isActive
											? "border-blue-600 text-blue-600"
											: "border-transparent text-gray-600 hover:text-gray-900",
										isRunning && !isActive && "opacity-50 cursor-not-allowed",
									)}
									data-testid={`algorithm-tab-${tab.id}`}
								>
									<Icon className="h-4 w-4" />
									<span>{tab.name}</span>
								</button>
							);
						})}
					</div>

					{/* Main Content Grid */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						{/* Left: Configuration */}
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center space-x-2">
									<span>配置</span>
									<span className="text-sm font-normal text-gray-500">
										{
											ALGORITHM_TABS.find((t) => t.id === activeAlgorithm)
												?.description
										}
									</span>
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-6">
								{/* KB Selector */}
								<KBSelector
									value={selectedKB}
									onChange={setSelectedKB}
									kbs={kbs}
									disabled={isRunning || kbsLoading}
								/>

								{/* Algorithm-specific config */}
								{renderConfigPanel()}

								{/* Cost Estimator */}
								{selectedKBInfo && (
									<CostEstimator
										algorithm={activeAlgorithm}
										kbChunkCount={selectedKBInfo.chunk_count}
										config={getCurrentConfig()}
									/>
								)}

								{/* Run Button */}
								<button
									type="button"
									onClick={handleRun}
									disabled={!selectedKB || isRunning}
									className={cn(
										"w-full flex items-center justify-center space-x-2 px-4 py-3 rounded-md text-white font-medium transition-colors",
										!selectedKB || isRunning
											? "bg-gray-400 cursor-not-allowed"
											: "bg-blue-600 hover:bg-blue-700",
									)}
									data-testid="run-algorithm-button"
								>
									<Play className="h-4 w-4" />
									<span>{isRunning ? "执行中..." : "开始执行"}</span>
								</button>
							</CardContent>
						</Card>

						{/* Right: Progress & Status */}
						<Card>
							<CardHeader>
								<CardTitle>执行状态</CardTitle>
							</CardHeader>
							<CardContent>
								{currentTaskId || currentTask ? (
									<AlgorithmProgressBar
										progress={progress}
										task={currentTask}
									/>
								) : (
									<div className="text-center py-8 text-gray-500">
										<GitBranch className="h-12 w-12 mx-auto mb-2 opacity-50" />
										<p>选择知识库并配置参数后开始执行</p>
									</div>
								)}
							</CardContent>
						</Card>
					</div>

					{/* History Section */}
					<Card>
						<CardHeader>
							<CardTitle>执行历史</CardTitle>
						</CardHeader>
						<CardContent>
							<RunHistoryTable tasks={historyTasks} loading={historyLoading} />
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
};

export default AlgorithmConsolePage;
