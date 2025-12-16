/**
 * CapabilityStorePage - 能力市场页面
 *
 * 展示所有可用能力，支持分类筛选、搜索和配置
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
 */

import { Crown, Rocket, Search, Sparkles, Store, Zap } from "lucide-react";
import * as React from "react";
import { CapabilityCard } from "@/components/CapabilityStore/CapabilityCard";
import { CapabilityConfigModal } from "@/components/CapabilityStore/CapabilityConfigModal";
import { cn } from "@/lib/utils";
import {
	type Capability,
	type CapabilityCategory,
	useCapabilityStore,
} from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

interface CategoryTab {
	id: CapabilityCategory | "all";
	name: string;
	icon: React.ElementType;
	description: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════════

const CATEGORY_TABS: CategoryTab[] = [
	{ id: "all", name: "全部", icon: Store, description: "所有能力" },
	{ id: "basic", name: "基础", icon: Zap, description: "基础能力" },
	{ id: "enhanced", name: "增强", icon: Sparkles, description: "增强能力" },
	{ id: "pro", name: "专业", icon: Crown, description: "专业能力" },
	{ id: "advanced", name: "高级", icon: Rocket, description: "高级能力" },
];

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

const CapabilityStorePage: React.FC = () => {
	// State
	const [activeCategory, setActiveCategory] = React.useState<
		CapabilityCategory | "all"
	>("all");
	const [searchQuery, setSearchQuery] = React.useState("");
	const [selectedCapability, setSelectedCapability] =
		React.useState<Capability | null>(null);
	const [configModalOpen, setConfigModalOpen] = React.useState(false);

	// Store
	const {
		capabilities,
		loading,
		error,
		fetchCapabilities,
		searchCapabilities,
	} = useCapabilityStore();

	// Load capabilities on mount
	React.useEffect(() => {
		fetchCapabilities();
	}, [fetchCapabilities]);

	// Filter capabilities based on category and search
	const filteredCapabilities = React.useMemo(() => {
		let caps: Capability[];

		// First filter by search if query exists
		if (searchQuery.trim()) {
			caps = searchCapabilities(searchQuery);
		} else {
			caps = Object.values(capabilities);
		}

		// Then filter by category
		if (activeCategory !== "all") {
			caps = caps.filter((cap) => cap.category === activeCategory);
		}

		return caps;
	}, [capabilities, activeCategory, searchQuery, searchCapabilities]);

	// Group capabilities by category for display
	const groupedCapabilities = React.useMemo(() => {
		if (activeCategory !== "all") {
			return { [activeCategory]: filteredCapabilities };
		}

		const groups: Record<string, Capability[]> = {};
		for (const cap of filteredCapabilities) {
			if (!groups[cap.category]) {
				groups[cap.category] = [];
			}
			groups[cap.category].push(cap);
		}
		return groups;
	}, [filteredCapabilities, activeCategory]);

	// Handlers
	const handleConfigure = (capability: Capability) => {
		setSelectedCapability(capability);
		setConfigModalOpen(true);
	};

	const handleCloseModal = () => {
		setConfigModalOpen(false);
		setSelectedCapability(null);
	};

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="bg-white border-b px-6 py-4">
				<div className="flex items-center justify-between">
					<div className="flex items-center space-x-2">
						<Store className="h-5 w-5 text-blue-600" />
						<h2 className="text-lg font-semibold text-gray-800">能力市场</h2>
					</div>
					<div className="flex items-center space-x-3">
						{/* Search Bar */}
						<div className="flex items-center border rounded-md px-3 py-1.5 bg-gray-50">
							<Search className="h-4 w-4 text-gray-400" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								placeholder="搜索能力..."
								className="px-2 py-0.5 text-sm outline-none bg-transparent w-48"
								data-testid="capability-search-input"
							/>
						</div>
					</div>
				</div>

				{/* Category Tabs */}
				<div className="flex items-center space-x-1 mt-4">
					{CATEGORY_TABS.map((tab) => {
						const Icon = tab.icon;
						const isActive = activeCategory === tab.id;
						return (
							<button
								key={tab.id}
								onClick={() => setActiveCategory(tab.id)}
								className={cn(
									"flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
									isActive
										? "bg-blue-100 text-blue-700"
										: "text-gray-600 hover:bg-gray-100",
								)}
								data-testid={`category-tab-${tab.id}`}
							>
								<Icon className="h-4 w-4" />
								<span>{tab.name}</span>
							</button>
						);
					})}
				</div>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-auto p-6">
				{loading ? (
					<div className="flex items-center justify-center h-64">
						<div className="text-gray-500">加载中...</div>
					</div>
				) : error ? (
					<div className="flex items-center justify-center h-64">
						<div className="text-red-500">{error}</div>
					</div>
				) : filteredCapabilities.length === 0 ? (
					<div className="flex flex-col items-center justify-center h-64 text-gray-500">
						<Store className="h-12 w-12 mb-2 opacity-50" />
						<p>没有找到匹配的能力</p>
						{searchQuery && (
							<button
								onClick={() => setSearchQuery("")}
								className="mt-2 text-blue-600 hover:underline text-sm"
							>
								清除搜索
							</button>
						)}
					</div>
				) : (
					<div className="space-y-8">
						{Object.entries(groupedCapabilities).map(([category, caps]) => {
							const categoryTab = CATEGORY_TABS.find((t) => t.id === category);
							const CategoryIcon = categoryTab?.icon || Store;

							return (
								<div key={category}>
									{activeCategory === "all" && (
										<div className="flex items-center space-x-2 mb-4">
											<CategoryIcon className="h-5 w-5 text-gray-600" />
											<h3 className="text-base font-medium text-gray-800">
												{categoryTab?.name || category}
											</h3>
											<span className="text-sm text-gray-400">
												({caps.length})
											</span>
										</div>
									)}
									<div
										className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
										data-testid={`capability-grid-${category}`}
									>
										{caps.map((capability) => (
											<CapabilityCard
												key={capability.id}
												capability={capability}
												onConfigure={() => handleConfigure(capability)}
											/>
										))}
									</div>
								</div>
							);
						})}
					</div>
				)}
			</div>

			{/* Config Modal */}
			{configModalOpen && selectedCapability && (
				<CapabilityConfigModal
					capability={selectedCapability}
					onClose={handleCloseModal}
				/>
			)}
		</div>
	);
};

export default CapabilityStorePage;
