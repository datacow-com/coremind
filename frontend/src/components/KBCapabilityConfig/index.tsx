/**
 * KBCapabilityConfig - KB 能力配置组件
 *
 * 显示 KB 已启用的能力列表，支持添加、配置和禁用能力
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
 */

import {
	AlertTriangle,
	CheckCircle,
	Loader2,
	Plus,
	Settings,
	Trash2,
	Zap,
} from "lucide-react";
import * as React from "react";
import { DynamicConfigForm } from "@/components/DynamicConfigForm";
import type { ValidationError } from "@/components/DynamicConfigForm/types";
import { useToast } from "@/components/ui/toast-provider";
import { cn } from "@/lib/utils";
import {
	type Capability,
	type CapabilitySettings,
	useCapabilityStore,
} from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface KBCapabilityConfigProps {
	/** Knowledge base name */
	kbName: string;
	/** Additional CSS classes */
	className?: string;
}

interface EnabledCapabilityItemProps {
	capability: Capability;
	settings: CapabilitySettings;
	onConfigure: () => void;
	onDisable: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sub-components
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * EnabledCapabilityItem - 已启用能力项
 */
const EnabledCapabilityItem: React.FC<EnabledCapabilityItemProps> = ({
	capability,
	settings: _settings,
	onConfigure,
	onDisable,
}) => {
	return (
		<div
			className="flex items-center justify-between p-4 bg-white border rounded-lg hover:shadow-sm transition-shadow"
			data-testid={`enabled-capability-${capability.id}`}
		>
			<div className="flex items-center space-x-3">
				<div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
					<Zap className="h-5 w-5 text-blue-600" />
				</div>
				<div>
					<h4 className="font-medium text-gray-900">{capability.name}</h4>
					<p className="text-sm text-gray-500 line-clamp-1">
						{capability.description}
					</p>
				</div>
			</div>
			<div className="flex items-center space-x-2">
				<CheckCircle className="h-4 w-4 text-green-500" />
				{capability.config_schema && (
					<button
						type="button"
						onClick={onConfigure}
						className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
						title="配置"
						data-testid={`configure-btn-${capability.id}`}
					>
						<Settings className="h-4 w-4" />
					</button>
				)}
				{!capability.always_on && (
					<button
						type="button"
						onClick={onDisable}
						className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
						title="禁用"
						data-testid={`disable-btn-${capability.id}`}
					>
						<Trash2 className="h-4 w-4" />
					</button>
				)}
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Add Capability Modal
// ═══════════════════════════════════════════════════════════════════════════════

interface AddCapabilityModalProps {
	kbName: string;
	enabledCapabilityIds: string[];
	onClose: () => void;
	onEnable: (capabilityId: string) => Promise<void>;
}

const AddCapabilityModal: React.FC<AddCapabilityModalProps> = ({
	kbName,
	enabledCapabilityIds,
	onClose,
	onEnable,
}) => {
	const { capabilities, checkDependencies } = useCapabilityStore();
	const [enabling, setEnabling] = React.useState<string | null>(null);
	const { push } = useToast();

	// Get available capabilities (not already enabled)
	const availableCapabilities = React.useMemo(() => {
		return Object.values(capabilities).filter(
			(cap) =>
				!enabledCapabilityIds.includes(cap.id) &&
				cap.user_configurable !== false,
		);
	}, [capabilities, enabledCapabilityIds]);

	const handleEnable = async (capability: Capability) => {
		// Check dependencies
		const { satisfied, missing } = checkDependencies(kbName, capability.id);
		if (!satisfied) {
			push({
				title: "依赖未满足",
				description: `需要先启用: ${missing.join(", ")}`,
				variant: "error",
			});
			return;
		}

		setEnabling(capability.id);
		try {
			await onEnable(capability.id);
			push({
				title: "能力已启用",
				description: `${capability.name} 已成功启用`,
				variant: "success",
			});
		} catch (error) {
			push({
				title: "启用失败",
				description: error instanceof Error ? error.message : "未知错误",
				variant: "error",
			});
		} finally {
			setEnabling(null);
		}
	};

	const handleBackdropClick = (e: React.MouseEvent) => {
		if (e.target === e.currentTarget) {
			onClose();
		}
	};

	return (
		<div
			role="dialog"
			aria-modal="true"
			className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
			onClick={handleBackdropClick}
			onKeyDown={(e) => e.key === "Escape" && onClose()}
			data-testid="add-capability-modal"
		>
			<div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b">
					<div className="flex items-center space-x-3">
						<Plus className="h-5 w-5 text-blue-600" />
						<h3 className="font-medium text-gray-900">添加能力</h3>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1 hover:bg-gray-100 rounded"
						aria-label="关闭"
					>
						×
					</button>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-auto p-6">
					{availableCapabilities.length === 0 ? (
						<div className="text-center py-8 text-gray-500">
							<p>所有能力都已启用</p>
						</div>
					) : (
						<div className="space-y-3">
							{availableCapabilities.map((capability) => {
								const { satisfied, missing } = checkDependencies(
									kbName,
									capability.id,
								);
								const isEnabling = enabling === capability.id;

								return (
									<div
										key={capability.id}
										className={cn(
											"flex items-center justify-between p-4 border rounded-lg",
											!satisfied && "opacity-60",
										)}
										data-testid={`available-capability-${capability.id}`}
									>
										<div className="flex-1">
											<h4 className="font-medium text-gray-900">
												{capability.name}
											</h4>
											<p className="text-sm text-gray-500 line-clamp-1">
												{capability.description}
											</p>
											{!satisfied && (
												<div className="flex items-center space-x-1 mt-1 text-amber-600 text-xs">
													<AlertTriangle className="h-3 w-3" />
													<span>需要: {missing.join(", ")}</span>
												</div>
											)}
										</div>
										<button
											type="button"
											onClick={() => handleEnable(capability)}
											disabled={!satisfied || isEnabling}
											className={cn(
												"flex items-center space-x-1 px-3 py-1.5 rounded-md text-sm",
												satisfied
													? "bg-blue-50 text-blue-700 hover:bg-blue-100"
													: "bg-gray-100 text-gray-400 cursor-not-allowed",
											)}
											data-testid={`enable-btn-${capability.id}`}
										>
											{isEnabling ? (
												<Loader2 className="h-4 w-4 animate-spin" />
											) : (
												<Plus className="h-4 w-4" />
											)}
											<span>启用</span>
										</button>
									</div>
								);
							})}
						</div>
					)}
				</div>

				{/* Footer */}
				<div className="flex items-center justify-end px-6 py-4 border-t bg-gray-50">
					<button
						type="button"
						onClick={onClose}
						className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
					>
						关闭
					</button>
				</div>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Configure Capability Modal
// ═══════════════════════════════════════════════════════════════════════════════

interface ConfigureCapabilityModalProps {
	capability: Capability;
	currentConfig: Record<string, unknown>;
	kbName: string;
	onClose: () => void;
	onSave: (config: Record<string, unknown>) => Promise<void>;
}

const ConfigureCapabilityModal: React.FC<ConfigureCapabilityModalProps> = ({
	capability,
	currentConfig,
	kbName: _kbName,
	onClose,
	onSave,
}) => {
	const [configValues, setConfigValues] =
		React.useState<Record<string, unknown>>(currentConfig);
	const [validationErrors, setValidationErrors] = React.useState<
		ValidationError[]
	>([]);
	const [saving, setSaving] = React.useState(false);
	const { push } = useToast();

	const handleSave = async () => {
		if (validationErrors.length > 0) {
			push({
				title: "配置验证失败",
				description: "请修正表单中的错误",
				variant: "error",
			});
			return;
		}

		setSaving(true);
		try {
			await onSave(configValues);
			push({
				title: "配置已保存",
				variant: "success",
			});
			onClose();
		} catch (error) {
			push({
				title: "保存失败",
				description: error instanceof Error ? error.message : "未知错误",
				variant: "error",
			});
		} finally {
			setSaving(false);
		}
	};

	const handleBackdropClick = (e: React.MouseEvent) => {
		if (e.target === e.currentTarget) {
			onClose();
		}
	};

	if (!capability.config_schema) {
		return null;
	}

	return (
		<div
			role="dialog"
			aria-modal="true"
			className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
			onClick={handleBackdropClick}
			onKeyDown={(e) => e.key === "Escape" && onClose()}
			data-testid="configure-capability-modal"
		>
			<div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b">
					<div className="flex items-center space-x-3">
						<Settings className="h-5 w-5 text-blue-600" />
						<div>
							<h3 className="font-medium text-gray-900">{capability.name}</h3>
							<p className="text-sm text-gray-500">配置能力参数</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1 hover:bg-gray-100 rounded"
						aria-label="关闭"
					>
						×
					</button>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-auto px-6 py-4">
					<DynamicConfigForm
						schema={capability.config_schema}
						value={configValues}
						onChange={setConfigValues}
						onValidate={setValidationErrors}
						errors={validationErrors}
					/>
				</div>

				{/* Footer */}
				<div className="flex items-center justify-end space-x-3 px-6 py-4 border-t bg-gray-50">
					<button
						type="button"
						onClick={onClose}
						className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
						disabled={saving}
					>
						取消
					</button>
					<button
						type="button"
						onClick={handleSave}
						disabled={saving}
						className={cn(
							"flex items-center space-x-2 px-4 py-2 text-sm rounded-md",
							"bg-blue-600 text-white hover:bg-blue-700",
							"disabled:opacity-50 disabled:cursor-not-allowed",
						)}
					>
						{saving ? (
							<>
								<Loader2 className="h-4 w-4 animate-spin" />
								<span>保存中...</span>
							</>
						) : (
							<span>保存配置</span>
						)}
					</button>
				</div>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Disable Confirmation Modal
// ═══════════════════════════════════════════════════════════════════════════════

interface DisableConfirmModalProps {
	capability: Capability;
	onConfirm: () => Promise<void>;
	onCancel: () => void;
}

const DisableConfirmModal: React.FC<DisableConfirmModalProps> = ({
	capability,
	onConfirm,
	onCancel,
}) => {
	const [disabling, setDisabling] = React.useState(false);
	const { push } = useToast();

	const handleConfirm = async () => {
		setDisabling(true);
		try {
			await onConfirm();
			push({
				title: "能力已禁用",
				description: `${capability.name} 已成功禁用`,
				variant: "success",
			});
		} catch (error) {
			push({
				title: "禁用失败",
				description: error instanceof Error ? error.message : "未知错误",
				variant: "error",
			});
		} finally {
			setDisabling(false);
		}
	};

	const handleBackdropClick = (e: React.MouseEvent) => {
		if (e.target === e.currentTarget) {
			onCancel();
		}
	};

	return (
		<div
			role="dialog"
			aria-modal="true"
			className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
			onClick={handleBackdropClick}
			onKeyDown={(e) => e.key === "Escape" && onCancel()}
			data-testid="disable-confirm-modal"
		>
			<div className="bg-white rounded-lg shadow-xl w-full max-w-md">
				<div className="p-6">
					<div className="flex items-center space-x-3 mb-4">
						<div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
							<AlertTriangle className="h-5 w-5 text-red-600" />
						</div>
						<h3 className="font-medium text-gray-900">确认禁用能力</h3>
					</div>
					<p className="text-sm text-gray-600 mb-4">
						确定要禁用 <strong>{capability.name}</strong> 吗？
						禁用后，该能力的配置将被保留，可以随时重新启用。
					</p>
					<div className="flex items-center justify-end space-x-3">
						<button
							type="button"
							onClick={onCancel}
							className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
							disabled={disabling}
						>
							取消
						</button>
						<button
							type="button"
							onClick={handleConfirm}
							disabled={disabling}
							className={cn(
								"flex items-center space-x-2 px-4 py-2 text-sm rounded-md",
								"bg-red-600 text-white hover:bg-red-700",
								"disabled:opacity-50 disabled:cursor-not-allowed",
							)}
							data-testid="confirm-disable-btn"
						>
							{disabling ? (
								<>
									<Loader2 className="h-4 w-4 animate-spin" />
									<span>禁用中...</span>
								</>
							) : (
								<span>确认禁用</span>
							)}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

export const KBCapabilityConfig: React.FC<KBCapabilityConfigProps> = ({
	kbName,
	className,
}) => {
	// State
	const [addModalOpen, setAddModalOpen] = React.useState(false);
	const [configureCapability, setConfigureCapability] =
		React.useState<Capability | null>(null);
	const [disableCapability, setDisableCapability] =
		React.useState<Capability | null>(null);

	// Store
	const {
		capabilities,
		kbConfigs,
		loading,
		error,
		fetchCapabilities,
		fetchKBConfig,
		enableCapability,
		disableCapability: disableCapabilityAction,
		updateKBCapability,
	} = useCapabilityStore();

	// Load data on mount
	React.useEffect(() => {
		fetchCapabilities();
		fetchKBConfig(kbName);
	}, [kbName, fetchCapabilities, fetchKBConfig]);

	// Get KB config
	const kbConfig = kbConfigs[kbName];

	// Get enabled capabilities with their settings
	const enabledCapabilities = React.useMemo(() => {
		if (!kbConfig?.capabilities) return [];

		const result: Array<{
			capability: Capability;
			settings: CapabilitySettings;
		}> = [];

		for (const [capId, settings] of Object.entries(kbConfig.capabilities)) {
			if (settings.enabled) {
				const capability = capabilities[capId];
				if (capability) {
					result.push({ capability, settings });
				}
			}
		}

		return result;
	}, [kbConfig, capabilities]);

	// Get enabled capability IDs
	const enabledCapabilityIds = React.useMemo(() => {
		return enabledCapabilities.map((item) => item.capability.id);
	}, [enabledCapabilities]);

	// Handlers
	const handleEnableCapability = async (capabilityId: string) => {
		const result = await enableCapability(kbName, capabilityId);
		if (!result.success && result.errors) {
			throw new Error(result.errors.map((e) => e.message).join(", "));
		}
		// Refresh KB config
		await fetchKBConfig(kbName);
	};

	const handleDisableCapability = async () => {
		if (!disableCapability) return;
		const result = await disableCapabilityAction(kbName, disableCapability.id);
		if (!result.success) {
			throw new Error("禁用失败");
		}
		setDisableCapability(null);
		// Refresh KB config
		await fetchKBConfig(kbName);
	};

	const handleSaveConfig = async (config: Record<string, unknown>) => {
		if (!configureCapability) return;
		const result = await updateKBCapability(kbName, configureCapability.id, {
			enabled: true,
			config,
		});
		if (!result.success && result.errors) {
			throw new Error(result.errors.map((e) => e.message).join(", "));
		}
		setConfigureCapability(null);
		// Refresh KB config
		await fetchKBConfig(kbName);
	};

	return (
		<div
			className={cn("space-y-4", className)}
			data-testid="kb-capability-config"
		>
			{/* Header */}
			<div className="flex items-center justify-between">
				<div>
					<h3 className="text-lg font-medium text-gray-900">能力配置</h3>
					<p className="text-sm text-gray-500">
						管理知识库 {kbName} 的能力配置
					</p>
				</div>
				<button
					type="button"
					onClick={() => setAddModalOpen(true)}
					className="flex items-center space-x-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
					data-testid="add-capability-btn"
				>
					<Plus className="h-4 w-4" />
					<span>添加能力</span>
				</button>
			</div>

			{/* Content */}
			{loading ? (
				<div className="flex items-center justify-center h-32">
					<Loader2 className="h-6 w-6 animate-spin text-blue-600" />
					<span className="ml-2 text-gray-500">加载中...</span>
				</div>
			) : error ? (
				<div className="text-center py-8 text-red-500">{error}</div>
			) : enabledCapabilities.length === 0 ? (
				<div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed">
					<Zap className="h-12 w-12 mx-auto text-gray-300 mb-3" />
					<p className="text-gray-500 mb-3">暂无启用的能力</p>
					<button
						type="button"
						onClick={() => setAddModalOpen(true)}
						className="text-blue-600 hover:underline text-sm"
					>
						添加第一个能力
					</button>
				</div>
			) : (
				<div className="space-y-3">
					{enabledCapabilities.map(({ capability, settings }) => (
						<EnabledCapabilityItem
							key={capability.id}
							capability={capability}
							settings={settings}
							onConfigure={() => setConfigureCapability(capability)}
							onDisable={() => setDisableCapability(capability)}
						/>
					))}
				</div>
			)}

			{/* Modals */}
			{addModalOpen && (
				<AddCapabilityModal
					kbName={kbName}
					enabledCapabilityIds={enabledCapabilityIds}
					onClose={() => setAddModalOpen(false)}
					onEnable={handleEnableCapability}
				/>
			)}

			{configureCapability && kbConfig && (
				<ConfigureCapabilityModal
					capability={configureCapability}
					currentConfig={
						kbConfig.capabilities[configureCapability.id]?.config || {}
					}
					kbName={kbName}
					onClose={() => setConfigureCapability(null)}
					onSave={handleSaveConfig}
				/>
			)}

			{disableCapability && (
				<DisableConfirmModal
					capability={disableCapability}
					onConfirm={handleDisableCapability}
					onCancel={() => setDisableCapability(null)}
				/>
			)}
		</div>
	);
};

export default KBCapabilityConfig;
