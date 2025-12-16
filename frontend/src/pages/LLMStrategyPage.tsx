/**
 * LLMStrategyPage - LLM 策略配置页面
 *
 * 配置 LLM 路由策略、预算限制和降级链
 *
 * Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
 */

import {
	AlertCircle,
	Check,
	ChevronDown,
	ChevronUp,
	DollarSign,
	GripVertical,
	Loader2,
	Save,
	Settings,
	Zap,
} from "lucide-react";
import * as React from "react";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export type RoutingStrategyType =
	| "default"
	| "cost_first"
	| "performance_first"
	| "balanced";

export interface RoutingStrategy {
	id: RoutingStrategyType;
	name: string;
	description: string;
}

export interface ProviderInfo {
	id: string;
	name: string;
	category: string;
	is_active: boolean;
	is_healthy: boolean;
	priority: number;
	is_domestic: boolean;
	models: string[];
}

export interface ProviderConfig {
	enabled: boolean;
	api_key?: string | null;
	base_url?: string | null;
	timeout: number;
	max_retries: number;
}

export interface LLMConfig {
	routing_strategy: RoutingStrategyType;
	budget_limit: number | null;
	fallback_chain: string[];
	provider_configs: Record<string, ProviderConfig>;
	default_provider: string | null;
	default_model: string | null;
	enable_cost_tracking: boolean;
}

export interface KBInfo {
	name: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// StrategySelector Component
// ═══════════════════════════════════════════════════════════════════════════════

interface StrategySelectorProps {
	strategies: RoutingStrategy[];
	selectedStrategy: RoutingStrategyType;
	onSelect: (strategy: RoutingStrategyType) => void;
	disabled?: boolean;
}

export const StrategySelector: React.FC<StrategySelectorProps> = ({
	strategies,
	selectedStrategy,
	onSelect,
	disabled,
}) => {
	return (
		<div className="space-y-3" data-testid="strategy-selector">
			{strategies.map((strategy) => (
				<button
					key={strategy.id}
					type="button"
					onClick={() => onSelect(strategy.id)}
					disabled={disabled}
					className={cn(
						"w-full text-left p-4 rounded-lg border-2 transition-all",
						selectedStrategy === strategy.id
							? "border-blue-500 bg-blue-50"
							: "border-gray-200 hover:border-gray-300 bg-white",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid={`strategy-option-${strategy.id}`}
				>
					<div className="flex items-center justify-between">
						<div>
							<h4 className="font-medium text-gray-900">{strategy.name}</h4>
							<p className="text-sm text-gray-500 mt-1">
								{strategy.description}
							</p>
						</div>
						{selectedStrategy === strategy.id && (
							<div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
								<Check className="h-4 w-4 text-white" />
							</div>
						)}
					</div>
				</button>
			))}
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// BudgetConfig Component
// ═══════════════════════════════════════════════════════════════════════════════

interface BudgetConfigProps {
	budgetLimit: number | null;
	currentUsage: number | null;
	enableCostTracking: boolean;
	onBudgetChange: (budget: number | null) => void;
	onCostTrackingChange: (enabled: boolean) => void;
	disabled?: boolean;
}

export const BudgetConfig: React.FC<BudgetConfigProps> = ({
	budgetLimit,
	currentUsage,
	enableCostTracking,
	onBudgetChange,
	onCostTrackingChange,
	disabled,
}) => {
	const [inputValue, setInputValue] = React.useState(
		budgetLimit?.toString() || "",
	);
	const [error, setError] = React.useState<string | null>(null);

	React.useEffect(() => {
		setInputValue(budgetLimit?.toString() || "");
	}, [budgetLimit]);

	const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const value = e.target.value;
		setInputValue(value);
		setError(null);

		if (value === "") {
			onBudgetChange(null);
			return;
		}

		const numValue = parseFloat(value);
		if (Number.isNaN(numValue)) {
			setError("请输入有效的数字");
			return;
		}
		if (numValue < 0) {
			setError("预算不能为负数");
			return;
		}
		onBudgetChange(numValue);
	};

	const usagePercentage =
		budgetLimit && currentUsage ? (currentUsage / budgetLimit) * 100 : 0;

	return (
		<div className="space-y-4" data-testid="budget-config">
			{/* Cost Tracking Toggle */}
			<div className="flex items-center justify-between">
				<div>
					<h4 className="font-medium text-gray-900">成本追踪</h4>
					<p className="text-sm text-gray-500">启用后将记录所有 LLM 调用成本</p>
				</div>
				<button
					type="button"
					onClick={() => onCostTrackingChange(!enableCostTracking)}
					disabled={disabled}
					className={cn(
						"relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
						enableCostTracking ? "bg-blue-600" : "bg-gray-200",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					data-testid="cost-tracking-toggle"
				>
					<span
						className={cn(
							"inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
							enableCostTracking ? "translate-x-6" : "translate-x-1",
						)}
					/>
				</button>
			</div>

			{/* Budget Limit Input */}
			<div className="space-y-2">
				<label
					htmlFor="budget-limit-input"
					className="text-sm font-medium text-gray-700"
				>
					预算限额 (USD)
				</label>
				<div className="relative">
					<DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
					<input
						id="budget-limit-input"
						type="number"
						value={inputValue}
						onChange={handleInputChange}
						placeholder="不设限制"
						disabled={disabled}
						min={0}
						step={0.01}
						className={cn(
							"w-full pl-9 pr-3 py-2 border rounded-md text-sm",
							"focus:outline-none focus:ring-2 focus:ring-blue-500",
							error ? "border-red-300" : "border-gray-300",
							disabled && "bg-gray-100 cursor-not-allowed",
						)}
						data-testid="budget-limit-input"
					/>
				</div>
				{error && (
					<p className="text-sm text-red-500 flex items-center space-x-1">
						<AlertCircle className="h-3 w-3" />
						<span>{error}</span>
					</p>
				)}
			</div>

			{/* Current Usage Display */}
			{enableCostTracking && (
				<div className="p-4 bg-gray-50 rounded-lg space-y-2">
					<div className="flex items-center justify-between text-sm">
						<span className="text-gray-600">当前使用量</span>
						<span className="font-medium text-gray-900">
							${currentUsage?.toFixed(4) || "0.0000"}
						</span>
					</div>
					{budgetLimit && (
						<>
							<div className="flex items-center justify-between text-sm">
								<span className="text-gray-600">预算限额</span>
								<span className="font-medium text-gray-900">
									${budgetLimit.toFixed(2)}
								</span>
							</div>
							<div className="w-full bg-gray-200 rounded-full h-2">
								<div
									className={cn(
										"h-2 rounded-full transition-all",
										usagePercentage > 90
											? "bg-red-500"
											: usagePercentage > 70
												? "bg-amber-500"
												: "bg-green-500",
									)}
									style={{ width: `${Math.min(usagePercentage, 100)}%` }}
									data-testid="usage-progress-bar"
								/>
							</div>
							<p className="text-xs text-gray-500 text-right">
								{usagePercentage.toFixed(1)}% 已使用
							</p>
						</>
					)}
				</div>
			)}
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// FallbackChainEditor Component
// ═══════════════════════════════════════════════════════════════════════════════

interface FallbackChainEditorProps {
	fallbackChain: string[];
	providers: ProviderInfo[];
	onChange: (chain: string[]) => void;
	disabled?: boolean;
}

export const FallbackChainEditor: React.FC<FallbackChainEditorProps> = ({
	fallbackChain,
	providers,
	onChange,
	disabled,
}) => {
	const [draggedIndex, setDraggedIndex] = React.useState<number | null>(null);
	const [dragOverIndex, setDragOverIndex] = React.useState<number | null>(null);

	// Get available models from providers
	const availableModels = React.useMemo(() => {
		const models: Array<{ provider: string; model: string; label: string }> =
			[];
		for (const provider of providers) {
			for (const model of provider.models) {
				models.push({
					provider: provider.id,
					model,
					label: `${provider.name} / ${model}`,
				});
			}
		}
		return models;
	}, [providers]);

	const handleDragStart = (index: number) => {
		if (disabled) return;
		setDraggedIndex(index);
	};

	const handleDragOver = (e: React.DragEvent, index: number) => {
		e.preventDefault();
		if (disabled) return;
		setDragOverIndex(index);
	};

	const handleDragEnd = () => {
		if (
			draggedIndex !== null &&
			dragOverIndex !== null &&
			draggedIndex !== dragOverIndex
		) {
			const newChain = [...fallbackChain];
			const [removed] = newChain.splice(draggedIndex, 1);
			newChain.splice(dragOverIndex, 0, removed);
			onChange(newChain);
		}
		setDraggedIndex(null);
		setDragOverIndex(null);
	};

	const handleMoveUp = (index: number) => {
		if (index === 0 || disabled) return;
		const newChain = [...fallbackChain];
		[newChain[index - 1], newChain[index]] = [
			newChain[index],
			newChain[index - 1],
		];
		onChange(newChain);
	};

	const handleMoveDown = (index: number) => {
		if (index === fallbackChain.length - 1 || disabled) return;
		const newChain = [...fallbackChain];
		[newChain[index], newChain[index + 1]] = [
			newChain[index + 1],
			newChain[index],
		];
		onChange(newChain);
	};

	const handleRemove = (index: number) => {
		if (disabled) return;
		const newChain = fallbackChain.filter((_, i) => i !== index);
		onChange(newChain);
	};

	const handleAdd = (modelKey: string) => {
		if (disabled || fallbackChain.includes(modelKey)) return;
		onChange([...fallbackChain, modelKey]);
	};

	// Models not in chain
	const availableToAdd = availableModels.filter(
		(m) => !fallbackChain.includes(`${m.provider}/${m.model}`),
	);

	return (
		<div className="space-y-4" data-testid="fallback-chain-editor">
			<div className="flex items-center justify-between">
				<div>
					<h4 className="font-medium text-gray-900">降级链</h4>
					<p className="text-sm text-gray-500">
						当主模型不可用时，按顺序尝试备选模型
					</p>
				</div>
			</div>

			{/* Current Chain */}
			<ul className="space-y-2 list-none p-0 m-0">
				{fallbackChain.length === 0 ? (
					<li className="p-4 border-2 border-dashed border-gray-200 rounded-lg text-center text-gray-500 text-sm">
						暂无降级链配置，请添加模型
					</li>
				) : (
					fallbackChain.map((item, index) => {
						const [providerId, modelId] = item.split("/");
						const provider = providers.find((p) => p.id === providerId);

						return (
							<li
								key={item}
								draggable={!disabled}
								onDragStart={() => handleDragStart(index)}
								onDragOver={(e) => handleDragOver(e, index)}
								onDragEnd={handleDragEnd}
								className={cn(
									"flex items-center space-x-3 p-3 bg-white border rounded-lg",
									draggedIndex === index && "opacity-50",
									dragOverIndex === index && "border-blue-500",
									disabled && "opacity-50",
								)}
								data-testid={`fallback-item-${index}`}
							>
								{/* Drag Handle */}
								<div
									className={cn(
										"cursor-grab text-gray-400",
										disabled && "cursor-not-allowed",
									)}
								>
									<GripVertical className="h-5 w-5" />
								</div>

								{/* Priority Number */}
								<div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-medium">
									{index + 1}
								</div>

								{/* Model Info */}
								<div className="flex-1">
									<div className="font-medium text-gray-900">
										{provider?.name || providerId}
									</div>
									<div className="text-sm text-gray-500">{modelId}</div>
								</div>

								{/* Health Status */}
								{provider && (
									<div
										className={cn(
											"w-2 h-2 rounded-full",
											provider.is_healthy ? "bg-green-500" : "bg-red-500",
										)}
										title={provider.is_healthy ? "健康" : "不可用"}
									/>
								)}

								{/* Move Buttons */}
								<div className="flex items-center space-x-1">
									<button
										type="button"
										onClick={() => handleMoveUp(index)}
										disabled={index === 0 || disabled}
										className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
										title="上移"
									>
										<ChevronUp className="h-4 w-4" />
									</button>
									<button
										type="button"
										onClick={() => handleMoveDown(index)}
										disabled={index === fallbackChain.length - 1 || disabled}
										className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
										title="下移"
									>
										<ChevronDown className="h-4 w-4" />
									</button>
								</div>

								{/* Remove Button */}
								<button
									type="button"
									onClick={() => handleRemove(index)}
									disabled={disabled}
									className="p-1 text-red-500 hover:bg-red-50 rounded disabled:opacity-30"
									title="移除"
								>
									×
								</button>
							</li>
						);
					})
				)}
			</ul>

			{/* Add Model Dropdown */}
			{availableToAdd.length > 0 && (
				<div className="space-y-2">
					<label
						htmlFor="add-model-select"
						className="text-sm font-medium text-gray-700"
					>
						添加模型
					</label>
					<select
						id="add-model-select"
						onChange={(e) => {
							if (e.target.value) {
								handleAdd(e.target.value);
								e.target.value = "";
							}
						}}
						disabled={disabled}
						className={cn(
							"w-full px-3 py-2 border border-gray-300 rounded-md text-sm",
							"focus:outline-none focus:ring-2 focus:ring-blue-500",
							disabled && "bg-gray-100 cursor-not-allowed",
						)}
						data-testid="add-model-select"
					>
						<option value="">选择要添加的模型...</option>
						{availableToAdd.map((m) => (
							<option
								key={`${m.provider}/${m.model}`}
								value={`${m.provider}/${m.model}`}
							>
								{m.label}
							</option>
						))}
					</select>
				</div>
			)}
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

interface LLMStrategyPageProps {
	kbName?: string;
}

const LLMStrategyPage: React.FC<LLMStrategyPageProps> = ({
	kbName: propKbName,
}) => {
	// State
	const [kbs, setKbs] = React.useState<KBInfo[]>([]);
	const [selectedKB, setSelectedKB] = React.useState<string>(propKbName || "");
	const [strategies, setStrategies] = React.useState<RoutingStrategy[]>([]);
	const [providers, setProviders] = React.useState<ProviderInfo[]>([]);
	const [config, setConfig] = React.useState<LLMConfig | null>(null);
	const [currentUsage, setCurrentUsage] = React.useState<number | null>(null);

	// Loading states
	const [loadingStrategies, setLoadingStrategies] = React.useState(true);
	const [loadingProviders, setLoadingProviders] = React.useState(true);
	const [loadingConfig, setLoadingConfig] = React.useState(false);
	const [saving, setSaving] = React.useState(false);

	// UI state
	const [error, setError] = React.useState<string | null>(null);
	const [saveSuccess, setSaveSuccess] = React.useState(false);
	const [hasChanges, setHasChanges] = React.useState(false);

	// Load KBs
	React.useEffect(() => {
		const loadKBs = async () => {
			try {
				const result = await apiJson<{ kbs: Array<{ name: string }> }>(
					"/api/kb",
				);
				if (result.ok && result.data) {
					setKbs(result.data.kbs.map((kb) => ({ name: kb.name })));
					// Auto-select first KB if none selected
					if (!selectedKB && result.data.kbs.length > 0) {
						setSelectedKB(result.data.kbs[0].name);
					}
				}
			} catch (err) {
				console.error("Failed to load KBs:", err);
			}
		};
		loadKBs();
	}, [selectedKB]);

	// Load routing strategies
	React.useEffect(() => {
		const loadStrategies = async () => {
			setLoadingStrategies(true);
			try {
				const result = await apiJson<{ strategies: RoutingStrategy[] }>(
					"/api/llm/routing-strategies",
				);
				if (result.ok && result.data) {
					setStrategies(result.data.strategies);
				}
			} catch (err) {
				console.error("Failed to load strategies:", err);
			} finally {
				setLoadingStrategies(false);
			}
		};
		loadStrategies();
	}, []);

	// Load providers
	React.useEffect(() => {
		const loadProviders = async () => {
			setLoadingProviders(true);
			try {
				const result = await apiJson<{ providers: ProviderInfo[] }>(
					"/api/llm/providers",
				);
				if (result.ok && result.data) {
					setProviders(result.data.providers);
				}
			} catch (err) {
				console.error("Failed to load providers:", err);
			} finally {
				setLoadingProviders(false);
			}
		};
		loadProviders();
	}, []);

	// Load KB LLM config when KB changes
	React.useEffect(() => {
		if (!selectedKB) {
			setConfig(null);
			return;
		}

		const loadConfig = async () => {
			setLoadingConfig(true);
			setError(null);
			setHasChanges(false);
			try {
				const result = await apiJson<{
					kb_name: string;
					config: LLMConfig;
					current_usage: number | null;
				}>(`/api/kb/${selectedKB}/llm-config`);
				if (result.ok && result.data) {
					setConfig(result.data.config);
					setCurrentUsage(result.data.current_usage);
				} else {
					// Initialize with defaults if not found
					setConfig({
						routing_strategy: "default",
						budget_limit: null,
						fallback_chain: [],
						provider_configs: {},
						default_provider: null,
						default_model: null,
						enable_cost_tracking: true,
					});
					setCurrentUsage(null);
				}
			} catch (err) {
				setError(err instanceof Error ? err.message : "加载配置失败");
			} finally {
				setLoadingConfig(false);
			}
		};
		loadConfig();
	}, [selectedKB]);

	// Handle config changes
	const updateConfig = (updates: Partial<LLMConfig>) => {
		if (!config) return;
		setConfig({ ...config, ...updates });
		setHasChanges(true);
		setSaveSuccess(false);
	};

	// Save configuration
	const handleSave = async () => {
		if (!selectedKB || !config) return;

		setSaving(true);
		setError(null);
		setSaveSuccess(false);

		try {
			const result = await apiJson<{
				kb_name: string;
				config: LLMConfig;
				updated_at: string;
				applied: boolean;
			}>(`/api/kb/${selectedKB}/llm-config`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					routing_strategy: config.routing_strategy,
					budget_limit: config.budget_limit,
					fallback_chain: config.fallback_chain,
					enable_cost_tracking: config.enable_cost_tracking,
				}),
			});

			if (result.ok && result.data) {
				setConfig(result.data.config);
				setHasChanges(false);
				setSaveSuccess(true);
				// Auto-hide success message after 3 seconds
				setTimeout(() => setSaveSuccess(false), 3000);
			} else {
				const errorData = result.data as unknown as { detail?: string };
				setError(errorData?.detail || "保存失败");
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "保存失败");
		} finally {
			setSaving(false);
		}
	};

	const isLoading = loadingStrategies || loadingProviders || loadingConfig;

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="bg-white border-b px-6 py-4">
				<div className="flex items-center justify-between">
					<div className="flex items-center space-x-2">
						<Zap className="h-5 w-5 text-amber-600" />
						<h2 className="text-lg font-semibold text-gray-800">
							LLM 策略配置
						</h2>
					</div>
					<div className="flex items-center space-x-3">
						{/* KB Selector */}
						<select
							value={selectedKB}
							onChange={(e) => setSelectedKB(e.target.value)}
							className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
							data-testid="kb-selector"
						>
							<option value="">选择知识库...</option>
							{kbs.map((kb) => (
								<option key={kb.name} value={kb.name}>
									{kb.name}
								</option>
							))}
						</select>

						{/* Save Button */}
						<button
							type="button"
							onClick={handleSave}
							disabled={!selectedKB || !hasChanges || saving}
							className={cn(
								"flex items-center space-x-2 px-4 py-1.5 rounded-md text-sm",
								"bg-blue-600 text-white hover:bg-blue-700",
								"disabled:opacity-50 disabled:cursor-not-allowed",
							)}
							data-testid="save-config-btn"
						>
							{saving ? (
								<>
									<Loader2 className="h-4 w-4 animate-spin" />
									<span>保存中...</span>
								</>
							) : (
								<>
									<Save className="h-4 w-4" />
									<span>保存配置</span>
								</>
							)}
						</button>
					</div>
				</div>
				<p className="text-sm text-gray-500 mt-1">
					配置 LLM 路由策略、预算限制和降级链
				</p>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-auto p-6">
				{!selectedKB ? (
					<div className="flex flex-col items-center justify-center h-64 text-gray-500">
						<Settings className="h-12 w-12 mb-2 opacity-50" />
						<p>请选择一个知识库以配置 LLM 策略</p>
					</div>
				) : isLoading ? (
					<div className="flex items-center justify-center h-64">
						<Loader2 className="h-6 w-6 animate-spin text-blue-600" />
						<span className="ml-2 text-gray-500">加载中...</span>
					</div>
				) : (
					<div className="max-w-3xl mx-auto space-y-8">
						{/* Error Message */}
						{error && (
							<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center space-x-2">
								<AlertCircle className="h-5 w-5" />
								<span>{error}</span>
							</div>
						)}

						{/* Success Message */}
						{saveSuccess && (
							<div
								className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 flex items-center space-x-2"
								data-testid="save-success-message"
							>
								<Check className="h-5 w-5" />
								<span>配置已保存并立即生效</span>
							</div>
						)}

						{/* Strategy Selection */}
						<section className="bg-white rounded-lg border p-6">
							<h3 className="text-lg font-medium text-gray-900 mb-4">
								路由策略
							</h3>
							<StrategySelector
								strategies={strategies}
								selectedStrategy={config?.routing_strategy || "default"}
								onSelect={(strategy) =>
									updateConfig({ routing_strategy: strategy })
								}
								disabled={saving}
							/>
						</section>

						{/* Budget Configuration */}
						<section className="bg-white rounded-lg border p-6">
							<h3 className="text-lg font-medium text-gray-900 mb-4">
								预算配置
							</h3>
							<BudgetConfig
								budgetLimit={config?.budget_limit || null}
								currentUsage={currentUsage}
								enableCostTracking={config?.enable_cost_tracking ?? true}
								onBudgetChange={(budget) =>
									updateConfig({ budget_limit: budget })
								}
								onCostTrackingChange={(enabled) =>
									updateConfig({ enable_cost_tracking: enabled })
								}
								disabled={saving}
							/>
						</section>

						{/* Fallback Chain */}
						<section className="bg-white rounded-lg border p-6">
							<h3 className="text-lg font-medium text-gray-900 mb-4">
								降级链配置
							</h3>
							<FallbackChainEditor
								fallbackChain={config?.fallback_chain || []}
								providers={providers}
								onChange={(chain) => updateConfig({ fallback_chain: chain })}
								disabled={saving}
							/>
						</section>
					</div>
				)}
			</div>
		</div>
	);
};

export default LLMStrategyPage;
