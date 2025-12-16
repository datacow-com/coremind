/**
 * CapabilityConfigModal - 能力配置弹窗组件
 *
 * 显示能力配置表单，支持动态表单生成和配置保存
 *
 * Requirements: 5.4
 */

import { Loader2, Save, Settings, X } from "lucide-react";
import * as React from "react";
import { DynamicConfigForm } from "@/components/DynamicConfigForm";
import type { ValidationError } from "@/components/DynamicConfigForm/types";
import { useToast } from "@/components/ui/toast-provider";
import { cn } from "@/lib/utils";
import {
	type Capability,
	type ConfigSchema,
	useCapabilityStore,
} from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface CapabilityConfigModalProps {
	/** Capability to configure */
	capability: Capability;
	/** KB name (optional - if provided, saves to KB config) */
	kbName?: string;
	/** Callback when modal is closed */
	onClose: () => void;
	/** Callback when configuration is saved */
	onSave?: (config: Record<string, unknown>) => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

export const CapabilityConfigModal: React.FC<CapabilityConfigModalProps> = ({
	capability,
	kbName,
	onClose,
	onSave,
}) => {
	// State
	const [configSchema, setConfigSchema] = React.useState<ConfigSchema | null>(
		capability.config_schema,
	);
	const [configValues, setConfigValues] = React.useState<
		Record<string, unknown>
	>({});
	const [validationErrors, setValidationErrors] = React.useState<
		ValidationError[]
	>([]);
	const [loading, setLoading] = React.useState(false);
	const [saving, setSaving] = React.useState(false);

	// Store
	const { getConfigSchema, getDefaultConfig, updateKBCapability } =
		useCapabilityStore();

	// Toast
	const { push } = useToast();

	// Load config schema and default values
	React.useEffect(() => {
		const loadConfig = async () => {
			setLoading(true);
			try {
				// Get config schema if not already available
				let schema = capability.config_schema;
				if (!schema) {
					schema = await getConfigSchema(capability.id);
					setConfigSchema(schema);
				}

				// Get default config values
				const defaultConfig = await getDefaultConfig(capability.id);
				if (defaultConfig) {
					setConfigValues(defaultConfig);
				} else if (schema) {
					// Build default values from schema
					const defaults: Record<string, unknown> = {};
					for (const [key, prop] of Object.entries(schema.properties)) {
						if (prop.default !== undefined) {
							defaults[key] = prop.default;
						}
					}
					setConfigValues(defaults);
				}
			} catch (error) {
				console.error("Failed to load config:", error);
				push({
					title: "加载配置失败",
					description: error instanceof Error ? error.message : "未知错误",
					variant: "error",
				});
			} finally {
				setLoading(false);
			}
		};

		loadConfig();
	}, [
		capability.id,
		capability.config_schema,
		getConfigSchema,
		getDefaultConfig,
		push,
	]);

	// Handle config value change
	const handleConfigChange = React.useCallback(
		(newValues: Record<string, unknown>) => {
			setConfigValues(newValues);
		},
		[],
	);

	// Handle validation
	const handleValidate = React.useCallback((errors: ValidationError[]) => {
		setValidationErrors(errors);
	}, []);

	// Handle save
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
			if (kbName) {
				// Save to KB configuration
				const result = await updateKBCapability(kbName, capability.id, {
					enabled: true,
					config: configValues,
				});

				if (result.success) {
					push({
						title: "配置已保存",
						variant: "success",
					});
					onSave?.(configValues);
					onClose();
				} else {
					push({
						title: "保存失败",
						description:
							result.errors?.map((e) => e.message).join(", ") || "未知错误",
						variant: "error",
					});
				}
			} else {
				// Just call onSave callback
				onSave?.(configValues);
				push({
					title: "配置已保存",
					variant: "success",
				});
				onClose();
			}
		} catch (error) {
			console.error("Failed to save config:", error);
			push({
				title: "保存失败",
				description: error instanceof Error ? error.message : "未知错误",
				variant: "error",
			});
		} finally {
			setSaving(false);
		}
	};

	// Handle backdrop click
	const handleBackdropClick = (e: React.MouseEvent) => {
		if (e.target === e.currentTarget) {
			onClose();
		}
	};

	return (
		<div
			className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
			onClick={handleBackdropClick}
			data-testid="capability-config-modal"
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
						onClick={onClose}
						className="p-1 hover:bg-gray-100 rounded"
						aria-label="关闭"
					>
						<X className="h-5 w-5 text-gray-500" />
					</button>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-auto px-6 py-4">
					{loading ? (
						<div className="flex items-center justify-center h-32">
							<Loader2 className="h-6 w-6 animate-spin text-blue-600" />
							<span className="ml-2 text-gray-500">加载配置...</span>
						</div>
					) : !configSchema ? (
						<div className="text-center py-8 text-gray-500">
							<p>此能力无需配置</p>
						</div>
					) : (
						<DynamicConfigForm
							schema={configSchema}
							value={configValues}
							onChange={handleConfigChange}
							onValidate={handleValidate}
							errors={validationErrors}
						/>
					)}
				</div>

				{/* Footer */}
				<div className="flex items-center justify-end space-x-3 px-6 py-4 border-t bg-gray-50">
					<button
						onClick={onClose}
						className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
						disabled={saving}
					>
						取消
					</button>
					<button
						onClick={handleSave}
						disabled={saving || loading || !configSchema}
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
							<>
								<Save className="h-4 w-4" />
								<span>保存配置</span>
							</>
						)}
					</button>
				</div>
			</div>
		</div>
	);
};

export default CapabilityConfigModal;
