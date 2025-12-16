/**
 * DomainManagerPage - 领域管理页面
 *
 * 展示所有已注册的领域，支持查看本体和绑定到 KB
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
 */

import {
	BookOpen,
	ChevronRight,
	FileType,
	Globe,
	Link2,
	Loader2,
	Search,
	Zap,
} from "lucide-react";
import * as React from "react";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface DomainInfo {
	id: string;
	name: string;
	description: string;
	icon: string;
	supported_formats: string[];
	requires: string[];
	requires_gpu: boolean;
	recommended_vram_mb: number;
	has_ontology: boolean;
}

export interface EntityDef {
	name: string;
	description: string;
	attributes: string[];
}

export interface RelationDef {
	name: string;
	from: string;
	to: string;
	description: string;
}

export interface OntologySchema {
	domain_id: string;
	version: string;
	entities: EntityDef[];
	relations: RelationDef[];
}

export interface KBInfo {
	name: string;
	chunk_count?: number;
}

export interface DomainBinding {
	kb_name: string;
	domain_id: string | null;
	config: Record<string, unknown>;
	is_bound: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DomainCard Component
// ═══════════════════════════════════════════════════════════════════════════════

interface DomainCardProps {
	domain: DomainInfo;
	onViewOntology: () => void;
	onBindToKB: () => void;
}

export const DomainCard: React.FC<DomainCardProps> = ({
	domain,
	onViewOntology,
	onBindToKB,
}) => {
	return (
		<div
			className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow"
			data-testid={`domain-card-${domain.id}`}
		>
			{/* Header */}
			<div className="flex items-start justify-between mb-3">
				<div className="flex items-center space-x-3">
					<div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center text-xl">
						{domain.icon || "📚"}
					</div>
					<div>
						<h3 className="font-medium text-gray-900">{domain.name}</h3>
						<p className="text-xs text-gray-500">{domain.id}</p>
					</div>
				</div>
				{domain.requires_gpu && (
					<span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full">
						GPU
					</span>
				)}
			</div>

			{/* Description */}
			<p className="text-sm text-gray-600 mb-3 line-clamp-2">
				{domain.description || "暂无描述"}
			</p>

			{/* Supported Formats */}
			{domain.supported_formats.length > 0 && (
				<div className="mb-3">
					<div className="flex items-center space-x-1 text-xs text-gray-500 mb-1">
						<FileType className="h-3 w-3" />
						<span>支持格式</span>
					</div>
					<div className="flex flex-wrap gap-1">
						{domain.supported_formats.map((format) => (
							<span
								key={format}
								className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
							>
								{format}
							</span>
						))}
					</div>
				</div>
			)}

			{/* Dependencies */}
			{domain.requires.length > 0 && (
				<div className="mb-3">
					<div className="flex items-center space-x-1 text-xs text-gray-500 mb-1">
						<Zap className="h-3 w-3" />
						<span>依赖能力</span>
					</div>
					<div className="flex flex-wrap gap-1">
						{domain.requires.map((req) => (
							<span
								key={req}
								className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded"
							>
								{req}
							</span>
						))}
					</div>
				</div>
			)}

			{/* Actions */}
			<div className="flex items-center space-x-2 pt-3 border-t">
				{domain.has_ontology && (
					<button
						type="button"
						onClick={onViewOntology}
						className="flex items-center space-x-1 px-3 py-1.5 text-sm text-purple-600 hover:bg-purple-50 rounded-md transition-colors"
						data-testid={`view-ontology-btn-${domain.id}`}
					>
						<BookOpen className="h-4 w-4" />
						<span>查看本体</span>
					</button>
				)}
				<button
					type="button"
					onClick={onBindToKB}
					className="flex items-center space-x-1 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
					data-testid={`bind-kb-btn-${domain.id}`}
				>
					<Link2 className="h-4 w-4" />
					<span>绑定 KB</span>
				</button>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// OntologyViewer Component
// ═══════════════════════════════════════════════════════════════════════════════

interface OntologyViewerProps {
	domain: DomainInfo;
	ontology: OntologySchema | null;
	loading: boolean;
	onClose: () => void;
}

export const OntologyViewer: React.FC<OntologyViewerProps> = ({
	domain,
	ontology,
	loading,
	onClose,
}) => {
	const [activeTab, setActiveTab] = React.useState<"entities" | "relations">(
		"entities",
	);

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
			data-testid="ontology-viewer-modal"
		>
			<div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b">
					<div className="flex items-center space-x-3">
						<div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center text-lg">
							{domain.icon || "📚"}
						</div>
						<div>
							<h3 className="font-medium text-gray-900">
								{domain.name} 本体定义
							</h3>
							{ontology && (
								<p className="text-xs text-gray-500">
									版本: {ontology.version}
								</p>
							)}
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

				{/* Tabs */}
				<div className="flex border-b px-6">
					<button
						type="button"
						onClick={() => setActiveTab("entities")}
						className={cn(
							"px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
							activeTab === "entities"
								? "border-purple-600 text-purple-600"
								: "border-transparent text-gray-600 hover:text-gray-900",
						)}
						data-testid="ontology-tab-entities"
					>
						实体 ({ontology?.entities.length || 0})
					</button>
					<button
						type="button"
						onClick={() => setActiveTab("relations")}
						className={cn(
							"px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
							activeTab === "relations"
								? "border-purple-600 text-purple-600"
								: "border-transparent text-gray-600 hover:text-gray-900",
						)}
						data-testid="ontology-tab-relations"
					>
						关系 ({ontology?.relations.length || 0})
					</button>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-auto p-6">
					{loading ? (
						<div className="flex items-center justify-center h-32">
							<Loader2 className="h-6 w-6 animate-spin text-purple-600" />
							<span className="ml-2 text-gray-500">加载中...</span>
						</div>
					) : !ontology ? (
						<div className="text-center py-8 text-gray-500">
							无法加载本体定义
						</div>
					) : activeTab === "entities" ? (
						<div className="space-y-4" data-testid="ontology-entities-list">
							{ontology.entities.length === 0 ? (
								<div className="text-center py-8 text-gray-500">
									暂无实体定义
								</div>
							) : (
								ontology.entities.map((entity) => (
									<div
										key={entity.name}
										className="border rounded-lg p-4"
										data-testid={`entity-${entity.name}`}
									>
										<h4 className="font-medium text-gray-900 mb-1">
											{entity.name}
										</h4>
										<p className="text-sm text-gray-600 mb-2">
											{entity.description || "暂无描述"}
										</p>
										{entity.attributes.length > 0 && (
											<div>
												<span className="text-xs text-gray-500">属性: </span>
												<div className="flex flex-wrap gap-1 mt-1">
													{entity.attributes.map((attr) => (
														<span
															key={attr}
															className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
														>
															{attr}
														</span>
													))}
												</div>
											</div>
										)}
									</div>
								))
							)}
						</div>
					) : (
						<div className="space-y-4" data-testid="ontology-relations-list">
							{ontology.relations.length === 0 ? (
								<div className="text-center py-8 text-gray-500">
									暂无关系定义
								</div>
							) : (
								ontology.relations.map((relation, index) => (
									<div
										key={`${relation.name}-${index}`}
										className="border rounded-lg p-4"
										data-testid={`relation-${relation.name}`}
									>
										<h4 className="font-medium text-gray-900 mb-2">
											{relation.name}
										</h4>
										<div className="flex items-center space-x-2 text-sm mb-2">
											<span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded">
												{relation.from}
											</span>
											<ChevronRight className="h-4 w-4 text-gray-400" />
											<span className="px-2 py-0.5 bg-green-50 text-green-600 rounded">
												{relation.to}
											</span>
										</div>
										<p className="text-sm text-gray-600">
											{relation.description || "暂无描述"}
										</p>
									</div>
								))
							)}
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
// DomainBindingModal Component
// ═══════════════════════════════════════════════════════════════════════════════

interface DomainBindingModalProps {
	domain: DomainInfo;
	kbs: KBInfo[];
	onBind: (kbName: string, config: Record<string, unknown>) => Promise<void>;
	onClose: () => void;
}

export const DomainBindingModal: React.FC<DomainBindingModalProps> = ({
	domain,
	kbs,
	onBind,
	onClose,
}) => {
	const [selectedKB, setSelectedKB] = React.useState("");
	const [binding, setBinding] = React.useState(false);
	const [error, setError] = React.useState<string | null>(null);

	const handleBind = async () => {
		if (!selectedKB) return;

		setBinding(true);
		setError(null);

		try {
			await onBind(selectedKB, {});
			onClose();
		} catch (err) {
			setError(err instanceof Error ? err.message : "绑定失败");
		} finally {
			setBinding(false);
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
			data-testid="domain-binding-modal"
		>
			<div className="bg-white rounded-lg shadow-xl w-full max-w-md">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b">
					<div className="flex items-center space-x-3">
						<Link2 className="h-5 w-5 text-blue-600" />
						<div>
							<h3 className="font-medium text-gray-900">绑定领域到 KB</h3>
							<p className="text-sm text-gray-500">{domain.name}</p>
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
				<div className="p-6 space-y-4">
					{/* KB Selector */}
					<div className="space-y-2">
						<label
							htmlFor="kb-selector-input"
							className="text-sm font-medium text-gray-700"
						>
							选择知识库
						</label>
						<select
							id="kb-selector-input"
							value={selectedKB}
							onChange={(e) => setSelectedKB(e.target.value)}
							disabled={binding}
							className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
							data-testid="kb-selector"
						>
							<option value="">选择知识库...</option>
							{kbs.map((kb) => (
								<option key={kb.name} value={kb.name}>
									{kb.name}
								</option>
							))}
						</select>
					</div>

					{/* Dependencies Warning */}
					{domain.requires.length > 0 && (
						<div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
							<div className="flex items-center space-x-2 text-amber-800 text-sm">
								<Zap className="h-4 w-4" />
								<span>此领域需要以下能力:</span>
							</div>
							<div className="flex flex-wrap gap-1 mt-2">
								{domain.requires.map((req) => (
									<span
										key={req}
										className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded"
									>
										{req}
									</span>
								))}
							</div>
						</div>
					)}

					{/* Error */}
					{error && (
						<div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
							{error}
						</div>
					)}
				</div>

				{/* Footer */}
				<div className="flex items-center justify-end space-x-3 px-6 py-4 border-t bg-gray-50">
					<button
						type="button"
						onClick={onClose}
						className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
						disabled={binding}
					>
						取消
					</button>
					<button
						type="button"
						onClick={handleBind}
						disabled={!selectedKB || binding}
						className={cn(
							"flex items-center space-x-2 px-4 py-2 text-sm rounded-md",
							"bg-blue-600 text-white hover:bg-blue-700",
							"disabled:opacity-50 disabled:cursor-not-allowed",
						)}
						data-testid="confirm-bind-btn"
					>
						{binding ? (
							<>
								<Loader2 className="h-4 w-4 animate-spin" />
								<span>绑定中...</span>
							</>
						) : (
							<span>确认绑定</span>
						)}
					</button>
				</div>
			</div>
		</div>
	);
};

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

const DomainManagerPage: React.FC = () => {
	// State
	const [domains, setDomains] = React.useState<DomainInfo[]>([]);
	const [loading, setLoading] = React.useState(true);
	const [error, setError] = React.useState<string | null>(null);
	const [searchQuery, setSearchQuery] = React.useState("");

	// Modal state
	const [selectedDomainForOntology, setSelectedDomainForOntology] =
		React.useState<DomainInfo | null>(null);
	const [ontology, setOntology] = React.useState<OntologySchema | null>(null);
	const [ontologyLoading, setOntologyLoading] = React.useState(false);

	const [selectedDomainForBinding, setSelectedDomainForBinding] =
		React.useState<DomainInfo | null>(null);
	const [kbs, setKbs] = React.useState<KBInfo[]>([]);

	// Load domains on mount
	React.useEffect(() => {
		const loadDomains = async () => {
			setLoading(true);
			setError(null);
			try {
				const result = await apiJson<{ domains: DomainInfo[]; total: number }>(
					"/api/domains",
				);
				if (result.ok && result.data) {
					setDomains(result.data.domains);
				} else {
					setError("加载领域列表失败");
				}
			} catch (err) {
				setError(err instanceof Error ? err.message : "未知错误");
			} finally {
				setLoading(false);
			}
		};
		loadDomains();
	}, []);

	// Load KBs for binding
	React.useEffect(() => {
		const loadKBs = async () => {
			try {
				const result = await apiJson<{ kbs: Array<{ name: string }> }>(
					"/api/kb",
				);
				if (result.ok && result.data) {
					setKbs(result.data.kbs.map((kb) => ({ name: kb.name })));
				}
			} catch (err) {
				console.error("Failed to load KBs:", err);
			}
		};
		loadKBs();
	}, []);

	// Filter domains by search
	const filteredDomains = React.useMemo(() => {
		if (!searchQuery.trim()) return domains;
		const query = searchQuery.toLowerCase();
		return domains.filter(
			(domain) =>
				domain.name.toLowerCase().includes(query) ||
				domain.id.toLowerCase().includes(query) ||
				domain.description.toLowerCase().includes(query),
		);
	}, [domains, searchQuery]);

	// Handle view ontology
	const handleViewOntology = async (domain: DomainInfo) => {
		setSelectedDomainForOntology(domain);
		setOntology(null);
		setOntologyLoading(true);

		try {
			const result = await apiJson<OntologySchema>(
				`/api/domains/${domain.id}/ontology`,
			);
			if (result.ok && result.data) {
				setOntology(result.data);
			}
		} catch (err) {
			console.error("Failed to load ontology:", err);
		} finally {
			setOntologyLoading(false);
		}
	};

	// Handle bind domain to KB
	const handleBindDomain = async (
		kbName: string,
		config: Record<string, unknown>,
	) => {
		if (!selectedDomainForBinding) return;

		const result = await apiJson<{ status: string }>(
			`/api/kb/${kbName}/domain`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					domain_id: selectedDomainForBinding.id,
					config,
				}),
			},
		);

		if (!result.ok) {
			const errorDetail = result.data as unknown as {
				detail?: { message?: string; missing?: string[] };
			};
			if (errorDetail?.detail?.missing) {
				throw new Error(`缺少依赖: ${errorDetail.detail.missing.join(", ")}`);
			}
			throw new Error(errorDetail?.detail?.message || "绑定失败");
		}
	};

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="bg-white border-b px-6 py-4">
				<div className="flex items-center justify-between">
					<div className="flex items-center space-x-2">
						<Globe className="h-5 w-5 text-purple-600" />
						<h2 className="text-lg font-semibold text-gray-800">领域管理</h2>
					</div>
					<div className="flex items-center space-x-3">
						{/* Search Bar */}
						<div className="flex items-center border rounded-md px-3 py-1.5 bg-gray-50">
							<Search className="h-4 w-4 text-gray-400" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								placeholder="搜索领域..."
								className="px-2 py-0.5 text-sm outline-none bg-transparent w-48"
								data-testid="domain-search-input"
							/>
						</div>
					</div>
				</div>
				<p className="text-sm text-gray-500 mt-1">
					管理垂直领域解读器，为知识库配置领域特定的解读能力
				</p>
			</div>

			{/* Content */}
			<div className="flex-1 overflow-auto p-6">
				{loading ? (
					<div className="flex items-center justify-center h-64">
						<Loader2 className="h-6 w-6 animate-spin text-purple-600" />
						<span className="ml-2 text-gray-500">加载中...</span>
					</div>
				) : error ? (
					<div className="flex items-center justify-center h-64">
						<div className="text-red-500">{error}</div>
					</div>
				) : filteredDomains.length === 0 ? (
					<div className="flex flex-col items-center justify-center h-64 text-gray-500">
						<Globe className="h-12 w-12 mb-2 opacity-50" />
						<p>{searchQuery ? "没有找到匹配的领域" : "暂无已注册的领域"}</p>
						{searchQuery && (
							<button
								type="button"
								onClick={() => setSearchQuery("")}
								className="mt-2 text-purple-600 hover:underline text-sm"
							>
								清除搜索
							</button>
						)}
					</div>
				) : (
					<div
						className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
						data-testid="domain-grid"
					>
						{filteredDomains.map((domain) => (
							<DomainCard
								key={domain.id}
								domain={domain}
								onViewOntology={() => handleViewOntology(domain)}
								onBindToKB={() => setSelectedDomainForBinding(domain)}
							/>
						))}
					</div>
				)}
			</div>

			{/* Ontology Viewer Modal */}
			{selectedDomainForOntology && (
				<OntologyViewer
					domain={selectedDomainForOntology}
					ontology={ontology}
					loading={ontologyLoading}
					onClose={() => setSelectedDomainForOntology(null)}
				/>
			)}

			{/* Domain Binding Modal */}
			{selectedDomainForBinding && (
				<DomainBindingModal
					domain={selectedDomainForBinding}
					kbs={kbs}
					onBind={handleBindDomain}
					onClose={() => setSelectedDomainForBinding(null)}
				/>
			)}
		</div>
	);
};

export default DomainManagerPage;
