/**
 * CapabilityCard - 能力卡片组件
 *
 * 显示单个能力的信息，包括名称、图标、描述、使用场景和配置状态
 *
 * Requirements: 5.3, 5.4
 */

import {
	CheckCircle,
	Cpu,
	Crown,
	Rocket,
	Settings,
	Sparkles,
	Zap,
} from "lucide-react";
import type * as React from "react";
import { cn } from "@/lib/utils";
import type { Capability, CapabilityCategory } from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface CapabilityCardProps {
	/** Capability data */
	capability: Capability;
	/** Whether the capability is enabled for current KB */
	isEnabled?: boolean;
	/** Callback when configure button is clicked */
	onConfigure?: () => void;
	/** Additional CSS classes */
	className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════════

const CATEGORY_COLORS: Record<
	CapabilityCategory,
	{ bg: string; text: string; border: string }
> = {
	basic: {
		bg: "bg-green-50",
		text: "text-green-700",
		border: "border-green-200",
	},
	enhanced: {
		bg: "bg-blue-50",
		text: "text-blue-700",
		border: "border-blue-200",
	},
	pro: {
		bg: "bg-purple-50",
		text: "text-purple-700",
		border: "border-purple-200",
	},
	advanced: {
		bg: "bg-orange-50",
		text: "text-orange-700",
		border: "border-orange-200",
	},
};

const CATEGORY_ICONS: Record<CapabilityCategory, React.ElementType> = {
	basic: Zap,
	enhanced: Sparkles,
	pro: Crown,
	advanced: Rocket,
};

const CATEGORY_LABELS: Record<CapabilityCategory, string> = {
	basic: "基础",
	enhanced: "增强",
	pro: "专业",
	advanced: "高级",
};

// ═══════════════════════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Get icon component from icon name string
 */
function getIconFromName(iconName: string): React.ElementType {
	// Map common icon names to Lucide icons
	const iconMap: Record<string, React.ElementType> = {
		zap: Zap,
		sparkles: Sparkles,
		crown: Crown,
		rocket: Rocket,
		cpu: Cpu,
		settings: Settings,
	};

	return iconMap[iconName.toLowerCase()] || Zap;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

export const CapabilityCard: React.FC<CapabilityCardProps> = ({
	capability,
	isEnabled = false,
	onConfigure,
	className,
}) => {
	const categoryColors = CATEGORY_COLORS[capability.category];
	const CategoryIcon = CATEGORY_ICONS[capability.category];
	const CapabilityIcon = getIconFromName(capability.icon);

	return (
		<div
			className={cn(
				"bg-white border rounded-lg p-4 hover:shadow-md transition-shadow",
				isEnabled && "ring-2 ring-blue-500",
				className,
			)}
			data-testid={`capability-card-${capability.id}`}
		>
			{/* Header */}
			<div className="flex items-start justify-between mb-3">
				<div className="flex items-center space-x-3">
					{/* Icon */}
					<div
						className={cn(
							"w-10 h-10 rounded-lg flex items-center justify-center",
							categoryColors.bg,
						)}
					>
						<CapabilityIcon className={cn("h-5 w-5", categoryColors.text)} />
					</div>
					{/* Name and Category */}
					<div>
						<h4 className="font-medium text-gray-900">{capability.name}</h4>
						<div className="flex items-center space-x-1.5 mt-0.5">
							<span
								className={cn(
									"inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-xs",
									categoryColors.bg,
									categoryColors.text,
								)}
							>
								<CategoryIcon className="h-3 w-3" />
								<span>{CATEGORY_LABELS[capability.category]}</span>
							</span>
							{capability.requires_gpu && (
								<span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
									<Cpu className="h-3 w-3" />
									<span>GPU</span>
								</span>
							)}
						</div>
					</div>
				</div>
				{/* Status indicator */}
				{isEnabled ? (
					<CheckCircle className="h-5 w-5 text-green-500" />
				) : capability.default_enabled ? (
					<span className="text-xs text-gray-400">默认启用</span>
				) : null}
			</div>

			{/* Description */}
			<p className="text-sm text-gray-600 mb-3 line-clamp-2">
				{capability.description}
			</p>

			{/* Use Case */}
			{capability.use_case && (
				<div className="mb-3">
					<span className="text-xs text-gray-500">适用场景：</span>
					<span className="text-xs text-gray-700 ml-1">
						{capability.use_case}
					</span>
				</div>
			)}

			{/* Dependencies */}
			{capability.requires && capability.requires.length > 0 && (
				<div className="mb-3">
					<span className="text-xs text-gray-500">依赖：</span>
					<span className="text-xs text-gray-700 ml-1">
						{capability.requires.join(", ")}
					</span>
				</div>
			)}

			{/* Footer */}
			<div className="flex items-center justify-between pt-3 border-t">
				<div className="flex items-center space-x-2">
					{capability.config_schema ? (
						<span className="text-xs text-gray-400">可配置</span>
					) : (
						<span className="text-xs text-gray-400">无需配置</span>
					)}
				</div>
				{capability.user_configurable !== false && (
					<button
						onClick={onConfigure}
						className={cn(
							"flex items-center space-x-1 px-3 py-1.5 rounded-md text-sm transition-colors",
							"bg-blue-50 text-blue-700 hover:bg-blue-100",
						)}
						data-testid={`configure-btn-${capability.id}`}
					>
						<Settings className="h-4 w-4" />
						<span>配置</span>
					</button>
				)}
			</div>
		</div>
	);
};

export default CapabilityCard;
