/**
 * Capability Store - 能力状态管理
 *
 * 管理能力列表、KB 配置、算法任务等状态
 *
 * Requirements: 5.1, 6.1
 */

import { create } from "zustand";
import { apiJson, buildSseRequest } from "@/lib/api";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Capability category types
 */
export type CapabilityCategory = "basic" | "enhanced" | "pro" | "advanced";

/**
 * Algorithm types
 */
export type AlgorithmType = "raptor" | "graphrag" | "mindmap";

/**
 * Algorithm execution mode
 */
export type AlgorithmMode = "light" | "deep";

/**
 * Task status
 */
export type TaskStatus = "pending" | "running" | "completed" | "failed";

/**
 * Property schema for config_schema
 */
export interface PropertySchema {
	type: string;
	title: string;
	description: string;
	enum?: string[];
	enum_labels?: Record<string, string>;
	minimum?: number;
	maximum?: number;
	default?: unknown;
	ui_component:
		| "select"
		| "slider"
		| "switch"
		| "input"
		| "multi-select"
		| "number"
		| "text";
	ui_step?: number;
	ui_show_if?: {
		field: string;
		value: unknown;
	};
	available_options?: Array<{ value: string; label: string }>;
}

/**
 * Config schema for capability
 */
export interface ConfigSchema {
	type: "object";
	properties: Record<string, PropertySchema>;
	required?: string[];
}

/**
 * Capability definition
 */
export interface Capability {
	id: string;
	name: string;
	name_en: string;
	description: string;
	description_en?: string;
	category: CapabilityCategory;
	icon: string;
	use_case: string;
	default_enabled: boolean;
	user_configurable?: boolean;
	always_on?: boolean;
	requires_gpu: boolean;
	gpu_memory_mb?: number;
	supported_formats?: string[];
	requires?: string[];
	config_schema: ConfigSchema | null;
	has_config?: boolean;
}

/**
 * Category definition
 */
export interface Category {
	id: CapabilityCategory;
	name: string;
	name_en: string;
	description: string;
}

/**
 * Capability settings for a KB
 */
export interface CapabilitySettings {
	enabled: boolean;
	config: Record<string, unknown>;
}

/**
 * KB capability configuration
 */
export interface KBCapabilityConfig {
	kb_name: string;
	capabilities: Record<string, CapabilitySettings>;
	updated_at?: string;
}

/**
 * Algorithm task
 */
export interface AlgorithmTask {
	task_id: string;
	algorithm: AlgorithmType;
	kb_name: string;
	mode: AlgorithmMode;
	status: TaskStatus;
	progress: number;
	stage: string;
	config: Record<string, unknown>;
	created_at: string;
	started_at?: string | null;
	completed_at?: string | null;
	error?: string | null;
	result?: Record<string, unknown> | null;
	estimated_cost: number;
	actual_cost?: number | null;
}

/**
 * Algorithm progress event
 */
export interface AlgorithmProgress {
	task_id: string;
	stage: string;
	progress: number;
	message: string;
	timestamp: string;
}

/**
 * Domain info
 */
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

/**
 * Validation error
 */
export interface ValidationError {
	capability_id: string;
	field: string;
	message: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Store Interface
// ═══════════════════════════════════════════════════════════════════════════════

export interface CapabilityStore {
	// ─────────────────────────────────────────────────────────────────────────────
	// State
	// ─────────────────────────────────────────────────────────────────────────────

	/** Capability list cache */
	capabilities: Record<string, Capability>;

	/** Category definitions */
	categories: Category[];

	/** Loading state */
	loading: boolean;

	/** Error message */
	error: string | null;

	/** KB configurations cache */
	kbConfigs: Record<string, KBCapabilityConfig>;

	/** Algorithm tasks cache */
	algorithmTasks: Record<string, AlgorithmTask>;

	/** Domain list cache */
	domains: DomainInfo[];

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Capability List
	// ─────────────────────────────────────────────────────────────────────────────

	/** Fetch all capabilities from server */
	fetchCapabilities: () => Promise<void>;

	/** Fetch categories from server */
	fetchCategories: () => Promise<void>;

	/** Get capability by ID */
	getCapability: (capabilityId: string) => Capability | undefined;

	/** Get capability config schema */
	getConfigSchema: (capabilityId: string) => Promise<ConfigSchema | null>;

	/** Get default config for capability */
	getDefaultConfig: (
		capabilityId: string,
	) => Promise<Record<string, unknown> | null>;

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - KB Configuration
	// ─────────────────────────────────────────────────────────────────────────────

	/** Fetch KB capability configuration */
	fetchKBConfig: (kbName: string) => Promise<KBCapabilityConfig | null>;

	/** Update KB capability configuration */
	updateKBCapability: (
		kbName: string,
		capabilityId: string,
		settings: CapabilitySettings,
	) => Promise<{ success: boolean; errors?: ValidationError[] }>;

	/** Enable a capability for KB */
	enableCapability: (
		kbName: string,
		capabilityId: string,
		config?: Record<string, unknown>,
	) => Promise<{ success: boolean; errors?: ValidationError[] }>;

	/** Disable a capability for KB */
	disableCapability: (
		kbName: string,
		capabilityId: string,
	) => Promise<{ success: boolean }>;

	/** Save all KB capabilities */
	saveKBCapabilities: (
		kbName: string,
		capabilities: Record<string, CapabilitySettings>,
	) => Promise<{ success: boolean; errors?: ValidationError[] }>;

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Algorithm Tasks
	// ─────────────────────────────────────────────────────────────────────────────

	/** Run an algorithm */
	runAlgorithm: (
		algorithm: AlgorithmType,
		kbName: string,
		mode: AlgorithmMode,
		config: Record<string, unknown>,
	) => Promise<string | null>;

	/** Get task status */
	getTaskStatus: (taskId: string) => Promise<AlgorithmTask | null>;

	/** Subscribe to task progress via SSE */
	subscribeToProgress: (
		taskId: string,
		onProgress: (progress: AlgorithmProgress) => void,
		onComplete?: (task: AlgorithmTask) => void,
		onError?: (error: string) => void,
	) => () => void;

	/** Fetch algorithm execution history */
	fetchAlgorithmHistory: (params?: {
		kb_name?: string;
		algorithm?: AlgorithmType;
		status?: TaskStatus;
		page?: number;
		page_size?: number;
	}) => Promise<{ tasks: AlgorithmTask[]; total: number }>;

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Domains
	// ─────────────────────────────────────────────────────────────────────────────

	/** Fetch all domains */
	fetchDomains: () => Promise<void>;

	// ─────────────────────────────────────────────────────────────────────────────
	// Selectors
	// ─────────────────────────────────────────────────────────────────────────────

	/** Get enabled capabilities for a KB */
	getEnabledCapabilities: (kbName: string) => Capability[];

	/** Get capabilities by category */
	getCapabilitiesByCategory: (category: CapabilityCategory) => Capability[];

	/** Search capabilities by name or description */
	searchCapabilities: (query: string) => Capability[];

	/** Check if capability dependencies are met */
	checkDependencies: (
		kbName: string,
		capabilityId: string,
	) => { satisfied: boolean; missing: string[] };

	// ─────────────────────────────────────────────────────────────────────────────
	// Internal
	// ─────────────────────────────────────────────────────────────────────────────

	/** Clear error */
	clearError: () => void;

	/** Set loading state */
	setLoading: (loading: boolean) => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Store Implementation
// ═══════════════════════════════════════════════════════════════════════════════

export const useCapabilityStore = create<CapabilityStore>((set, get) => ({
	// ─────────────────────────────────────────────────────────────────────────────
	// Initial State
	// ─────────────────────────────────────────────────────────────────────────────

	capabilities: {},
	categories: [],
	loading: false,
	error: null,
	kbConfigs: {},
	algorithmTasks: {},
	domains: [],

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Capability List
	// ─────────────────────────────────────────────────────────────────────────────

	fetchCapabilities: async () => {
		set({ loading: true, error: null });
		try {
			const result = await apiJson<Capability[]>("/api/capabilities/list");
			if (result.ok && result.data) {
				const capMap: Record<string, Capability> = {};
				for (const cap of result.data) {
					capMap[cap.id] = cap;
				}
				set({ capabilities: capMap, loading: false });
			} else {
				set({
					error: result.error?.message || "Failed to fetch capabilities",
					loading: false,
				});
			}
		} catch (err) {
			set({
				error: err instanceof Error ? err.message : "Unknown error",
				loading: false,
			});
		}
	},

	fetchCategories: async () => {
		try {
			const result = await apiJson<Category[]>("/api/capabilities/categories");
			if (result.ok && result.data) {
				set({ categories: result.data });
			}
		} catch (err) {
			console.error("Failed to fetch categories:", err);
		}
	},

	getCapability: (capabilityId: string) => {
		return get().capabilities[capabilityId];
	},

	getConfigSchema: async (capabilityId: string) => {
		try {
			const result = await apiJson<ConfigSchema>(
				`/api/capabilities/config-schema/${capabilityId}`,
			);
			if (result.ok && result.data) {
				return result.data;
			}
			return null;
		} catch {
			return null;
		}
	},

	getDefaultConfig: async (capabilityId: string) => {
		try {
			const result = await apiJson<Record<string, unknown>>(
				`/api/capabilities/default-config/${capabilityId}`,
			);
			if (result.ok && result.data) {
				return result.data;
			}
			return null;
		} catch {
			return null;
		}
	},

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - KB Configuration
	// ─────────────────────────────────────────────────────────────────────────────

	fetchKBConfig: async (kbName: string) => {
		set({ loading: true, error: null });
		try {
			const result = await apiJson<KBCapabilityConfig>(
				`/api/kb/${kbName}/capabilities`,
			);
			if (result.ok && result.data) {
				set((state) => ({
					kbConfigs: {
						...state.kbConfigs,
						[kbName]: result.data!,
					},
					loading: false,
				}));
				return result.data;
			} else {
				set({
					error: result.error?.message || "Failed to fetch KB config",
					loading: false,
				});
				return null;
			}
		} catch (err) {
			set({
				error: err instanceof Error ? err.message : "Unknown error",
				loading: false,
			});
			return null;
		}
	},

	updateKBCapability: async (
		kbName: string,
		capabilityId: string,
		settings: CapabilitySettings,
	) => {
		const currentConfig = get().kbConfigs[kbName];
		const capabilities = currentConfig?.capabilities || {};

		const newCapabilities = {
			...capabilities,
			[capabilityId]: settings,
		};

		return get().saveKBCapabilities(kbName, newCapabilities);
	},

	enableCapability: async (
		kbName: string,
		capabilityId: string,
		config?: Record<string, unknown>,
	) => {
		// Check dependencies first
		const { satisfied, missing } = get().checkDependencies(
			kbName,
			capabilityId,
		);
		if (!satisfied) {
			return {
				success: false,
				errors: missing.map((dep) => ({
					capability_id: capabilityId,
					field: "requires",
					message: `Missing dependency: ${dep}`,
				})),
			};
		}

		// Get default config if not provided
		let finalConfig = config;
		if (!finalConfig) {
			finalConfig = (await get().getDefaultConfig(capabilityId)) || {};
		}

		return get().updateKBCapability(kbName, capabilityId, {
			enabled: true,
			config: finalConfig,
		});
	},

	disableCapability: async (kbName: string, capabilityId: string) => {
		const currentConfig = get().kbConfigs[kbName];
		const capabilities = currentConfig?.capabilities || {};
		const currentSettings = capabilities[capabilityId];

		// Keep the config but disable
		return get().updateKBCapability(kbName, capabilityId, {
			enabled: false,
			config: currentSettings?.config || {},
		});
	},

	saveKBCapabilities: async (
		kbName: string,
		capabilities: Record<string, CapabilitySettings>,
	) => {
		set({ loading: true, error: null });
		try {
			const result = await apiJson<{
				kb_name: string;
				capabilities: Record<string, CapabilitySettings>;
				updated_at: string;
				validation_errors: ValidationError[];
			}>(`/api/kb/${kbName}/capabilities`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ capabilities }),
			});

			if (result.ok && result.data) {
				set((state) => ({
					kbConfigs: {
						...state.kbConfigs,
						[kbName]: {
							kb_name: result.data!.kb_name,
							capabilities: result.data!.capabilities,
							updated_at: result.data!.updated_at,
						},
					},
					loading: false,
				}));
				return { success: true };
			} else {
				const errors =
					result.data?.validation_errors ||
					(result.error?.detail?.errors as ValidationError[]) ||
					[];
				set({
					error: result.error?.message || "Failed to save KB capabilities",
					loading: false,
				});
				return { success: false, errors };
			}
		} catch (err) {
			set({
				error: err instanceof Error ? err.message : "Unknown error",
				loading: false,
			});
			return { success: false };
		}
	},

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Algorithm Tasks
	// ─────────────────────────────────────────────────────────────────────────────

	runAlgorithm: async (
		algorithm: AlgorithmType,
		kbName: string,
		mode: AlgorithmMode,
		config: Record<string, unknown>,
	) => {
		set({ loading: true, error: null });
		try {
			const result = await apiJson<{
				task_id: string;
				algorithm: AlgorithmType;
				kb_name: string;
				status: TaskStatus;
				message: string;
			}>(`/api/algorithms/${algorithm}/run`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ kb_name: kbName, mode, config }),
			});

			if (result.ok && result.data) {
				set({ loading: false });
				return result.data.task_id;
			} else {
				set({
					error: result.error?.message || "Failed to start algorithm",
					loading: false,
				});
				return null;
			}
		} catch (err) {
			set({
				error: err instanceof Error ? err.message : "Unknown error",
				loading: false,
			});
			return null;
		}
	},

	getTaskStatus: async (taskId: string) => {
		try {
			const result = await apiJson<{ task: AlgorithmTask }>(
				`/api/algorithms/${taskId}/status`,
			);
			if (result.ok && result.data) {
				const task = result.data.task;
				set((state) => ({
					algorithmTasks: {
						...state.algorithmTasks,
						[taskId]: task,
					},
				}));
				return task;
			}
			return null;
		} catch {
			return null;
		}
	},

	subscribeToProgress: (
		taskId: string,
		onProgress: (progress: AlgorithmProgress) => void,
		onComplete?: (task: AlgorithmTask) => void,
		onError?: (error: string) => void,
	) => {
		const { url } = buildSseRequest(`/api/algorithms/${taskId}/progress`);
		const eventSource = new EventSource(url);

		const handleMessage = (event: MessageEvent) => {
			try {
				const data = JSON.parse(event.data);

				// Check for close event
				if (data.type === "close") {
					eventSource.close();
					if (data.reason === "completed" && onComplete) {
						get()
							.getTaskStatus(taskId)
							.then((task) => {
								if (task) onComplete(task);
							});
					} else if (data.reason === "failed" && onError) {
						onError("Task failed");
					}
					return;
				}

				// Progress event
				const progress: AlgorithmProgress = {
					task_id: data.task_id || taskId,
					stage: data.stage || "",
					progress: data.progress || 0,
					message: data.message || "",
					timestamp: data.timestamp || new Date().toISOString(),
				};

				onProgress(progress);

				// Update task in store
				set((state) => {
					const existingTask = state.algorithmTasks[taskId];
					if (existingTask) {
						return {
							algorithmTasks: {
								...state.algorithmTasks,
								[taskId]: {
									...existingTask,
									progress: progress.progress,
									stage: progress.stage,
								},
							},
						};
					}
					return state;
				});

				// Check for completion
				if (progress.stage === "completed" || progress.stage === "failed") {
					eventSource.close();
					if (progress.stage === "completed" && onComplete) {
						get()
							.getTaskStatus(taskId)
							.then((task) => {
								if (task) onComplete(task);
							});
					} else if (progress.stage === "failed" && onError) {
						onError(progress.message);
					}
				}
			} catch (err) {
				console.error("Failed to parse SSE message:", err);
			}
		};

		const handleError = (event: Event) => {
			console.error("SSE error:", event);
			eventSource.close();
			if (onError) {
				onError("Connection lost");
			}
		};

		eventSource.addEventListener("message", handleMessage);
		eventSource.addEventListener("error", handleError);

		// Return cleanup function
		return () => {
			eventSource.removeEventListener("message", handleMessage);
			eventSource.removeEventListener("error", handleError);
			eventSource.close();
		};
	},

	fetchAlgorithmHistory: async (params = {}) => {
		try {
			const queryParams = new URLSearchParams();
			if (params.kb_name) queryParams.set("kb_name", params.kb_name);
			if (params.algorithm) queryParams.set("algorithm", params.algorithm);
			if (params.status) queryParams.set("status", params.status);
			if (params.page) queryParams.set("page", String(params.page));
			if (params.page_size)
				queryParams.set("page_size", String(params.page_size));

			const url = `/api/algorithms/history${queryParams.toString() ? `?${queryParams}` : ""}`;
			const result = await apiJson<{
				tasks: AlgorithmTask[];
				total: number;
				page: number;
				page_size: number;
			}>(url);

			if (result.ok && result.data) {
				// Update tasks in store
				set((state) => {
					const newTasks = { ...state.algorithmTasks };
					for (const task of result.data!.tasks) {
						newTasks[task.task_id] = task;
					}
					return { algorithmTasks: newTasks };
				});
				return { tasks: result.data.tasks, total: result.data.total };
			}
			return { tasks: [], total: 0 };
		} catch {
			return { tasks: [], total: 0 };
		}
	},

	// ─────────────────────────────────────────────────────────────────────────────
	// Actions - Domains
	// ─────────────────────────────────────────────────────────────────────────────

	fetchDomains: async () => {
		try {
			const result = await apiJson<{ domains: DomainInfo[]; total: number }>(
				"/api/domains",
			);
			if (result.ok && result.data) {
				set({ domains: result.data.domains });
			}
		} catch (err) {
			console.error("Failed to fetch domains:", err);
		}
	},

	// ─────────────────────────────────────────────────────────────────────────────
	// Selectors
	// ─────────────────────────────────────────────────────────────────────────────

	getEnabledCapabilities: (kbName: string) => {
		const state = get();
		const kbConfig = state.kbConfigs[kbName];
		if (!kbConfig) return [];

		const enabledCaps: Capability[] = [];
		for (const [capId, settings] of Object.entries(kbConfig.capabilities)) {
			if (settings.enabled) {
				const cap = state.capabilities[capId];
				if (cap) {
					enabledCaps.push(cap);
				}
			}
		}
		return enabledCaps;
	},

	getCapabilitiesByCategory: (category: CapabilityCategory) => {
		const state = get();
		return Object.values(state.capabilities).filter(
			(cap) => cap.category === category,
		);
	},

	searchCapabilities: (query: string) => {
		const state = get();
		const lowerQuery = query.toLowerCase();
		return Object.values(state.capabilities).filter(
			(cap) =>
				cap.name.toLowerCase().includes(lowerQuery) ||
				cap.name_en.toLowerCase().includes(lowerQuery) ||
				cap.description.toLowerCase().includes(lowerQuery) ||
				(cap.description_en?.toLowerCase().includes(lowerQuery) ?? false),
		);
	},

	checkDependencies: (kbName: string, capabilityId: string) => {
		const state = get();
		const capability = state.capabilities[capabilityId];
		if (
			!capability ||
			!capability.requires ||
			capability.requires.length === 0
		) {
			return { satisfied: true, missing: [] };
		}

		const kbConfig = state.kbConfigs[kbName];
		const enabledCaps = kbConfig?.capabilities || {};

		const missing: string[] = [];
		for (const req of capability.requires) {
			const reqSettings = enabledCaps[req];
			if (!reqSettings || !reqSettings.enabled) {
				missing.push(req);
			}
		}

		return {
			satisfied: missing.length === 0,
			missing,
		};
	},

	// ─────────────────────────────────────────────────────────────────────────────
	// Internal
	// ─────────────────────────────────────────────────────────────────────────────

	clearError: () => set({ error: null }),

	setLoading: (loading: boolean) => set({ loading }),
}));

// ═══════════════════════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Get capability store state (for use outside React components)
 */
export const getCapabilityState = () => useCapabilityStore.getState();
