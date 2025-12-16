/**
 * Capability Search Filtering Property-Based Tests
 *
 * **Feature: capability-visualization, Property 8: Capability Search Filtering**
 * **Validates: Requirements 5.5**
 *
 * For any search query, the filtered capabilities should only include those
 * whose name or description contains the search term (case-insensitive).
 */

import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import type { Capability, CapabilityCategory } from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Search Filter Implementation (extracted for testing)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Filter capabilities by search query
 * Matches against name, name_en, description, and description_en (case-insensitive)
 */
export function filterCapabilitiesBySearch(
	capabilities: Capability[],
	query: string,
): Capability[] {
	if (!query.trim()) {
		return capabilities;
	}

	const lowerQuery = query.toLowerCase();
	return capabilities.filter(
		(cap) =>
			cap.name.toLowerCase().includes(lowerQuery) ||
			cap.name_en.toLowerCase().includes(lowerQuery) ||
			cap.description.toLowerCase().includes(lowerQuery) ||
			(cap.description_en?.toLowerCase().includes(lowerQuery) ?? false),
	);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Arbitraries (Generators)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Generate a valid capability category
 */
const categoryArb: fc.Arbitrary<CapabilityCategory> = fc.constantFrom(
	"basic",
	"enhanced",
	"pro",
	"advanced",
);

/**
 * Generate a non-empty string for names/descriptions
 */
const nonEmptyStringArb = fc
	.string({ minLength: 1, maxLength: 50 })
	.filter((s) => s.trim().length > 0);

/**
 * Generate a capability ID
 */
const capabilityIdArb = fc.stringMatching(/^[a-z][a-z0-9_-]{2,20}$/);

/**
 * Generate a valid Capability object
 */
const capabilityArb: fc.Arbitrary<Capability> = fc.record({
	id: capabilityIdArb,
	name: nonEmptyStringArb,
	name_en: nonEmptyStringArb,
	description: nonEmptyStringArb,
	description_en: fc.option(nonEmptyStringArb, { nil: undefined }),
	category: categoryArb,
	icon: fc.constantFrom("zap", "sparkles", "crown", "rocket"),
	use_case: nonEmptyStringArb,
	default_enabled: fc.boolean(),
	user_configurable: fc.boolean(),
	always_on: fc.boolean(),
	requires_gpu: fc.boolean(),
	gpu_memory_mb: fc.integer({ min: 0, max: 16000 }),
	supported_formats: fc.array(fc.constantFrom("pdf", "docx", "txt", "md"), {
		minLength: 0,
		maxLength: 4,
	}),
	requires: fc.array(capabilityIdArb, { minLength: 0, maxLength: 3 }),
	config_schema: fc.constant(null),
});

/**
 * Generate a list of capabilities
 */
const capabilityListArb = fc.array(capabilityArb, {
	minLength: 0,
	maxLength: 20,
});

/**
 * Generate a search query (can be empty or non-empty)
 */
const searchQueryArb = fc.string({ minLength: 0, maxLength: 30 });

// ═══════════════════════════════════════════════════════════════════════════════
// Property Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe("Property 8: Capability Search Filtering", () => {
	/**
	 * **Feature: capability-visualization, Property 8: Capability Search Filtering**
	 * **Validates: Requirements 5.5**
	 */

	it("should return all capabilities when search query is empty", () => {
		fc.assert(
			fc.property(capabilityListArb, (capabilities) => {
				const result = filterCapabilitiesBySearch(capabilities, "");
				expect(result).toEqual(capabilities);
			}),
			{ numRuns: 100 },
		);
	});

	it("should return all capabilities when search query is whitespace only", () => {
		fc.assert(
			fc.property(
				capabilityListArb,
				fc.constantFrom("   ", "\t", "\n", "  \t  ", "\n\n"),
				(capabilities, whitespace) => {
					const result = filterCapabilitiesBySearch(capabilities, whitespace);
					expect(result).toEqual(capabilities);
				},
			),
			{ numRuns: 100 },
		);
	});

	it("should only include capabilities whose name or description contains the search term (case-insensitive)", () => {
		fc.assert(
			fc.property(
				capabilityListArb,
				searchQueryArb.filter((q) => q.trim().length > 0),
				(capabilities, query) => {
					const result = filterCapabilitiesBySearch(capabilities, query);
					const lowerQuery = query.toLowerCase();

					// Every result should contain the query in name or description
					for (const cap of result) {
						const matchesName = cap.name.toLowerCase().includes(lowerQuery);
						const matchesNameEn = cap.name_en
							.toLowerCase()
							.includes(lowerQuery);
						const matchesDesc = cap.description
							.toLowerCase()
							.includes(lowerQuery);
						const matchesDescEn =
							cap.description_en?.toLowerCase().includes(lowerQuery) ?? false;

						expect(
							matchesName || matchesNameEn || matchesDesc || matchesDescEn,
						).toBe(true);
					}
				},
			),
			{ numRuns: 100 },
		);
	});

	it("should not exclude any capability that matches the search term", () => {
		fc.assert(
			fc.property(
				capabilityListArb,
				searchQueryArb.filter((q) => q.trim().length > 0),
				(capabilities, query) => {
					const result = filterCapabilitiesBySearch(capabilities, query);
					const lowerQuery = query.toLowerCase();

					// Every capability that matches should be in the result
					for (const cap of capabilities) {
						const matchesName = cap.name.toLowerCase().includes(lowerQuery);
						const matchesNameEn = cap.name_en
							.toLowerCase()
							.includes(lowerQuery);
						const matchesDesc = cap.description
							.toLowerCase()
							.includes(lowerQuery);
						const matchesDescEn =
							cap.description_en?.toLowerCase().includes(lowerQuery) ?? false;

						if (matchesName || matchesNameEn || matchesDesc || matchesDescEn) {
							expect(result).toContainEqual(cap);
						}
					}
				},
			),
			{ numRuns: 100 },
		);
	});

	it("should be case-insensitive", () => {
		fc.assert(
			fc.property(
				capabilityListArb,
				nonEmptyStringArb,
				(capabilities, query) => {
					const lowerResult = filterCapabilitiesBySearch(
						capabilities,
						query.toLowerCase(),
					);
					const upperResult = filterCapabilitiesBySearch(
						capabilities,
						query.toUpperCase(),
					);
					const mixedResult = filterCapabilitiesBySearch(capabilities, query);

					// All case variations should return the same results
					expect(lowerResult).toEqual(upperResult);
					expect(lowerResult).toEqual(mixedResult);
				},
			),
			{ numRuns: 100 },
		);
	});

	it("should return empty array when no capabilities match", () => {
		// Create capabilities with known content that won't match our search
		const capabilities: Capability[] = [
			{
				id: "test-cap-1",
				name: "测试能力",
				name_en: "Test Capability",
				description: "这是一个测试能力",
				category: "basic",
				icon: "zap",
				use_case: "测试用途",
				default_enabled: true,
				requires_gpu: false,
				config_schema: null,
			},
		];

		// Search for something that definitely won't match
		const result = filterCapabilitiesBySearch(capabilities, "xyz123notfound");
		expect(result).toEqual([]);
	});

	it("should preserve the order of capabilities", () => {
		fc.assert(
			fc.property(capabilityListArb, searchQueryArb, (capabilities, query) => {
				const result = filterCapabilitiesBySearch(capabilities, query);

				// Check that the order is preserved
				let lastIndex = -1;
				for (const cap of result) {
					const currentIndex = capabilities.findIndex((c) => c.id === cap.id);
					expect(currentIndex).toBeGreaterThan(lastIndex);
					lastIndex = currentIndex;
				}
			}),
			{ numRuns: 100 },
		);
	});

	it("should handle special characters in search query", () => {
		const capabilities: Capability[] = [
			{
				id: "special-cap",
				name: "特殊能力 (测试)",
				name_en: "Special Capability [Test]",
				description: "包含特殊字符: @#$%",
				category: "basic",
				icon: "zap",
				use_case: "测试",
				default_enabled: true,
				requires_gpu: false,
				config_schema: null,
			},
		];

		// Search with special characters
		expect(filterCapabilitiesBySearch(capabilities, "(测试)")).toHaveLength(1);
		expect(filterCapabilitiesBySearch(capabilities, "[Test]")).toHaveLength(1);
		expect(filterCapabilitiesBySearch(capabilities, "@#$")).toHaveLength(1);
	});

	it("should match partial strings", () => {
		fc.assert(
			fc.property(
				capabilityArb,
				fc.integer({ min: 0, max: 10 }),
				fc.integer({ min: 1, max: 10 }),
				(capability, start, length) => {
					// Extract a substring from the capability name
					const name = capability.name;
					if (name.length < start + length) {
						return; // Skip if name is too short
					}

					const substring = name.substring(start, start + length);
					if (!substring.trim()) {
						return; // Skip empty substrings
					}

					const result = filterCapabilitiesBySearch([capability], substring);
					expect(result).toContainEqual(capability);
				},
			),
			{ numRuns: 100 },
		);
	});
});
