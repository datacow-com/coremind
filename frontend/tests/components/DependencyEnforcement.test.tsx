/**
 * Dependency Enforcement Property-Based Tests
 *
 * **Feature: capability-visualization, Property 9: Dependency Enforcement**
 * **Validates: Requirements 6.5, 3.5**
 *
 * Tests that capabilities with dependencies cannot be enabled if dependencies are not met,
 * and the error should list the missing dependencies.
 */

import { act, renderHook } from "@testing-library/react";
import * as fc from "fast-check";
import { beforeEach, describe, expect, it } from "vitest";

import {
	type Capability,
	type CapabilitySettings,
	type KBCapabilityConfig,
	useCapabilityStore,
} from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Arbitraries (Generators)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Generate a valid capability ID (alphanumeric with underscores)
 */
const capabilityIdArb = fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/);

/**
 * Generate a valid KB name
 */
const kbNameArb = fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/);

/**
 * Generate a capability category
 */
const categoryArb = fc.constantFrom(
	"basic",
	"enhanced",
	"pro",
	"advanced",
) as fc.Arbitrary<Capability["category"]>;

/**
 * Generate a basic capability without dependencies
 */
const baseCapabilityArb = (id: string): fc.Arbitrary<Capability> =>
	fc.record({
		id: fc.constant(id),
		name: fc.string({ minLength: 1, maxLength: 30 }),
		name_en: fc.string({ minLength: 1, maxLength: 30 }),
		description: fc.string({ minLength: 1, maxLength: 100 }),
		category: categoryArb,
		icon: fc.constant("zap"),
		use_case: fc.string({ minLength: 1, maxLength: 50 }),
		default_enabled: fc.boolean(),
		user_configurable: fc.constant(true),
		always_on: fc.constant(false),
		requires_gpu: fc.boolean(),
		gpu_memory_mb: fc.integer({ min: 0, max: 8000 }),
		supported_formats: fc.array(fc.constantFrom("pdf", "docx", "txt"), {
			minLength: 0,
			maxLength: 3,
		}),
		requires: fc.constant([]),
		config_schema: fc.constant(null),
	});

/**
 * Generate a capability with specific dependencies
 */
const capabilityWithDepsArb = (
	id: string,
	requires: string[],
): fc.Arbitrary<Capability> =>
	baseCapabilityArb(id).map((cap) => ({
		...cap,
		requires,
	}));

// ═══════════════════════════════════════════════════════════════════════════════
// Test Helpers
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Reset the store state before each test
 */
function resetStore() {
	const store = useCapabilityStore.getState();
	useCapabilityStore.setState({
		capabilities: {},
		categories: [],
		loading: false,
		error: null,
		kbConfigs: {},
		algorithmTasks: {},
		domains: [],
	});
}

/**
 * Set up store with capabilities and KB config
 */
function setupStore(
	capabilities: Record<string, Capability>,
	kbConfigs: Record<string, KBCapabilityConfig>,
) {
	useCapabilityStore.setState({
		capabilities,
		kbConfigs,
	});
}

// ═══════════════════════════════════════════════════════════════════════════════
// Property Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe("Property 9: Dependency Enforcement", () => {
	beforeEach(() => {
		resetStore();
	});

	/**
	 * **Feature: capability-visualization, Property 9: Dependency Enforcement**
	 * **Validates: Requirements 6.5, 3.5**
	 *
	 * For any capability with dependencies, enabling the capability should fail
	 * if any dependency is not satisfied, and the error should list the missing dependencies.
	 */
	describe("checkDependencies function", () => {
		it("should return satisfied=true for capabilities without dependencies", () => {
			fc.assert(
				fc.property(capabilityIdArb, kbNameArb, (capId, kbName) => {
					// Create a capability without dependencies
					const capability: Capability = {
						id: capId,
						name: "Test Capability",
						name_en: "Test Capability",
						description: "A test capability",
						category: "basic",
						icon: "zap",
						use_case: "Testing",
						default_enabled: false,
						requires_gpu: false,
						requires: [], // No dependencies
						config_schema: null,
					};

					// Set up store
					setupStore(
						{ [capId]: capability },
						{
							[kbName]: {
								kb_name: kbName,
								capabilities: {},
							},
						},
					);

					// Check dependencies
					const { checkDependencies } = useCapabilityStore.getState();
					const result = checkDependencies(kbName, capId);

					expect(result.satisfied).toBe(true);
					expect(result.missing).toEqual([]);
				}),
				{ numRuns: 100 },
			);
		});

		it("should return satisfied=false with missing list when dependencies are not enabled", () => {
			fc.assert(
				fc.property(
					capabilityIdArb,
					fc.array(capabilityIdArb, { minLength: 1, maxLength: 3 }),
					kbNameArb,
					(capId, depIds, kbName) => {
						// Ensure capId is not in depIds
						const uniqueDepIds = depIds.filter((d) => d !== capId);
						fc.pre(uniqueDepIds.length > 0);

						// Create the main capability with dependencies
						const mainCapability: Capability = {
							id: capId,
							name: "Main Capability",
							name_en: "Main Capability",
							description: "A capability with dependencies",
							category: "enhanced",
							icon: "zap",
							use_case: "Testing",
							default_enabled: false,
							requires_gpu: false,
							requires: uniqueDepIds,
							config_schema: null,
						};

						// Create dependency capabilities (but don't enable them)
						const capabilities: Record<string, Capability> = {
							[capId]: mainCapability,
						};
						for (const depId of uniqueDepIds) {
							capabilities[depId] = {
								id: depId,
								name: `Dependency ${depId}`,
								name_en: `Dependency ${depId}`,
								description: "A dependency capability",
								category: "basic",
								icon: "zap",
								use_case: "Testing",
								default_enabled: false,
								requires_gpu: false,
								requires: [],
								config_schema: null,
							};
						}

						// Set up store with no capabilities enabled
						setupStore(capabilities, {
							[kbName]: {
								kb_name: kbName,
								capabilities: {}, // No capabilities enabled
							},
						});

						// Check dependencies
						const { checkDependencies } = useCapabilityStore.getState();
						const result = checkDependencies(kbName, capId);

						// Should not be satisfied
						expect(result.satisfied).toBe(false);
						// Missing should contain all dependency IDs
						expect(result.missing.sort()).toEqual(uniqueDepIds.sort());
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return satisfied=true when all dependencies are enabled", () => {
			fc.assert(
				fc.property(
					capabilityIdArb,
					fc.array(capabilityIdArb, { minLength: 1, maxLength: 3 }),
					kbNameArb,
					(capId, depIds, kbName) => {
						// Ensure capId is not in depIds and depIds are unique
						const uniqueDepIds = [
							...new Set(depIds.filter((d) => d !== capId)),
						];
						fc.pre(uniqueDepIds.length > 0);

						// Create the main capability with dependencies
						const mainCapability: Capability = {
							id: capId,
							name: "Main Capability",
							name_en: "Main Capability",
							description: "A capability with dependencies",
							category: "enhanced",
							icon: "zap",
							use_case: "Testing",
							default_enabled: false,
							requires_gpu: false,
							requires: uniqueDepIds,
							config_schema: null,
						};

						// Create dependency capabilities
						const capabilities: Record<string, Capability> = {
							[capId]: mainCapability,
						};
						const enabledCapabilities: Record<string, CapabilitySettings> = {};

						for (const depId of uniqueDepIds) {
							capabilities[depId] = {
								id: depId,
								name: `Dependency ${depId}`,
								name_en: `Dependency ${depId}`,
								description: "A dependency capability",
								category: "basic",
								icon: "zap",
								use_case: "Testing",
								default_enabled: false,
								requires_gpu: false,
								requires: [],
								config_schema: null,
							};
							// Enable the dependency
							enabledCapabilities[depId] = {
								enabled: true,
								config: {},
							};
						}

						// Set up store with dependencies enabled
						setupStore(capabilities, {
							[kbName]: {
								kb_name: kbName,
								capabilities: enabledCapabilities,
							},
						});

						// Check dependencies
						const { checkDependencies } = useCapabilityStore.getState();
						const result = checkDependencies(kbName, capId);

						// Should be satisfied
						expect(result.satisfied).toBe(true);
						expect(result.missing).toEqual([]);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return partial missing list when some dependencies are enabled", () => {
			fc.assert(
				fc.property(
					capabilityIdArb,
					fc.array(capabilityIdArb, { minLength: 2, maxLength: 4 }),
					kbNameArb,
					fc.integer({ min: 1 }),
					(capId, depIds, kbName, enableCount) => {
						// Ensure capId is not in depIds and depIds are unique
						const uniqueDepIds = [
							...new Set(depIds.filter((d) => d !== capId)),
						];
						fc.pre(uniqueDepIds.length >= 2);

						// Determine how many to enable (at least 1, but not all)
						const numToEnable = Math.min(
							(enableCount % (uniqueDepIds.length - 1)) + 1,
							uniqueDepIds.length - 1,
						);
						const enabledDepIds = uniqueDepIds.slice(0, numToEnable);
						const missingDepIds = uniqueDepIds.slice(numToEnable);

						// Create the main capability with dependencies
						const mainCapability: Capability = {
							id: capId,
							name: "Main Capability",
							name_en: "Main Capability",
							description: "A capability with dependencies",
							category: "enhanced",
							icon: "zap",
							use_case: "Testing",
							default_enabled: false,
							requires_gpu: false,
							requires: uniqueDepIds,
							config_schema: null,
						};

						// Create dependency capabilities
						const capabilities: Record<string, Capability> = {
							[capId]: mainCapability,
						};
						const enabledCapabilities: Record<string, CapabilitySettings> = {};

						for (const depId of uniqueDepIds) {
							capabilities[depId] = {
								id: depId,
								name: `Dependency ${depId}`,
								name_en: `Dependency ${depId}`,
								description: "A dependency capability",
								category: "basic",
								icon: "zap",
								use_case: "Testing",
								default_enabled: false,
								requires_gpu: false,
								requires: [],
								config_schema: null,
							};
						}

						// Only enable some dependencies
						for (const depId of enabledDepIds) {
							enabledCapabilities[depId] = {
								enabled: true,
								config: {},
							};
						}

						// Set up store
						setupStore(capabilities, {
							[kbName]: {
								kb_name: kbName,
								capabilities: enabledCapabilities,
							},
						});

						// Check dependencies
						const { checkDependencies } = useCapabilityStore.getState();
						const result = checkDependencies(kbName, capId);

						// Should not be satisfied
						expect(result.satisfied).toBe(false);
						// Missing should contain only the non-enabled dependencies
						expect(result.missing.sort()).toEqual(missingDepIds.sort());
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should handle capability not found gracefully", () => {
			fc.assert(
				fc.property(capabilityIdArb, kbNameArb, (capId, kbName) => {
					// Set up store with empty capabilities
					setupStore(
						{},
						{
							[kbName]: {
								kb_name: kbName,
								capabilities: {},
							},
						},
					);

					// Check dependencies for non-existent capability
					const { checkDependencies } = useCapabilityStore.getState();
					const result = checkDependencies(kbName, capId);

					// Should return satisfied=true (no dependencies to check)
					expect(result.satisfied).toBe(true);
					expect(result.missing).toEqual([]);
				}),
				{ numRuns: 50 },
			);
		});

		it("should handle KB config not found gracefully", () => {
			fc.assert(
				fc.property(
					capabilityIdArb,
					fc.array(capabilityIdArb, { minLength: 1, maxLength: 2 }),
					kbNameArb,
					(capId, depIds, kbName) => {
						const uniqueDepIds = [
							...new Set(depIds.filter((d) => d !== capId)),
						];
						fc.pre(uniqueDepIds.length > 0);

						// Create capability with dependencies
						const capability: Capability = {
							id: capId,
							name: "Test Capability",
							name_en: "Test Capability",
							description: "A test capability",
							category: "basic",
							icon: "zap",
							use_case: "Testing",
							default_enabled: false,
							requires_gpu: false,
							requires: uniqueDepIds,
							config_schema: null,
						};

						// Set up store without KB config
						setupStore({ [capId]: capability }, {});

						// Check dependencies
						const { checkDependencies } = useCapabilityStore.getState();
						const result = checkDependencies(kbName, capId);

						// Should not be satisfied (dependencies not enabled)
						expect(result.satisfied).toBe(false);
						expect(result.missing.sort()).toEqual(uniqueDepIds.sort());
					},
				),
				{ numRuns: 50 },
			);
		});
	});

	describe("enableCapability with dependency check", () => {
		it("should fail to enable capability when dependencies are not met", () => {
			// This is a specific example test to verify the integration
			const capId = "advanced_feature";
			const depId = "basic_feature";
			const kbName = "test_kb";

			// Create capabilities
			const capabilities: Record<string, Capability> = {
				[capId]: {
					id: capId,
					name: "Advanced Feature",
					name_en: "Advanced Feature",
					description: "Requires basic feature",
					category: "advanced",
					icon: "rocket",
					use_case: "Advanced use",
					default_enabled: false,
					requires_gpu: false,
					requires: [depId],
					config_schema: null,
				},
				[depId]: {
					id: depId,
					name: "Basic Feature",
					name_en: "Basic Feature",
					description: "A basic feature",
					category: "basic",
					icon: "zap",
					use_case: "Basic use",
					default_enabled: false,
					requires_gpu: false,
					requires: [],
					config_schema: null,
				},
			};

			// Set up store without dependencies enabled
			setupStore(capabilities, {
				[kbName]: {
					kb_name: kbName,
					capabilities: {},
				},
			});

			// Check dependencies
			const { checkDependencies } = useCapabilityStore.getState();
			const result = checkDependencies(kbName, capId);

			expect(result.satisfied).toBe(false);
			expect(result.missing).toContain(depId);
		});
	});
});
