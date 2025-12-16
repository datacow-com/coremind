/**
 * DynamicConfigForm Property-Based Tests
 *
 * **Feature: capability-visualization, Property 7: Conditional Field Visibility**
 * **Validates: Requirements 7.5**
 *
 * Tests that fields with ui_show_if conditions are visible only when
 * the referenced field has the specified value.
 */

import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import { DynamicConfigForm } from "@/components/DynamicConfigForm";
import { isFieldVisible } from "@/components/DynamicConfigForm/utils";
import type { ConfigSchema, PropertySchema } from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Arbitraries (Generators)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Generate a valid field name (alphanumeric, starting with letter)
 */
const fieldNameArb = fc.stringMatching(/^[a-z][a-z0-9_]{0,19}$/);

/**
 * Generate a primitive value for form fields
 */
const primitiveValueArb = fc.oneof(
	fc.string({ minLength: 0, maxLength: 20 }),
	fc.integer({ min: -1000, max: 1000 }),
	fc.boolean(),
);

/**
 * Generate a ui_component type
 */
const uiComponentArb = fc.constantFrom(
	"select",
	"slider",
	"switch",
	"input",
	"multi-select",
	"number",
	"text",
) as fc.Arbitrary<PropertySchema["ui_component"]>;

/**
 * Generate a basic PropertySchema without ui_show_if
 */
const basePropertySchemaArb = fc.record({
	type: fc.constantFrom("string", "integer", "boolean", "number"),
	title: fc.string({ minLength: 1, maxLength: 30 }),
	description: fc.string({ minLength: 0, maxLength: 100 }),
	ui_component: uiComponentArb,
	default: primitiveValueArb,
});

/**
 * Generate a PropertySchema with ui_show_if condition
 */
const conditionalPropertySchemaArb = (
	controlFieldName: string,
	controlValue: unknown,
) =>
	basePropertySchemaArb.map((base) => ({
		...base,
		ui_show_if: {
			field: controlFieldName,
			value: controlValue,
		},
	}));

// ═══════════════════════════════════════════════════════════════════════════════
// Property Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe("Property 7: Conditional Field Visibility", () => {
	/**
	 * **Feature: capability-visualization, Property 7: Conditional Field Visibility**
	 * **Validates: Requirements 7.5**
	 *
	 * For any config_schema property with ui_show_if condition,
	 * the field should be visible only when the referenced field has the specified value.
	 */
	describe("isFieldVisible utility function", () => {
		it("should return true for fields without ui_show_if", () => {
			fc.assert(
				fc.property(
					basePropertySchemaArb,
					fc.dictionary(fieldNameArb, primitiveValueArb),
					(schema, formValues) => {
						// Fields without ui_show_if should always be visible
						const result = isFieldVisible(schema as PropertySchema, formValues);
						expect(result).toBe(true);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return true when ui_show_if condition is satisfied (exact match)", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					primitiveValueArb,
					basePropertySchemaArb,
					(controlField, controlValue, baseSchema) => {
						// Create schema with ui_show_if
						const schema: PropertySchema = {
							...(baseSchema as PropertySchema),
							ui_show_if: {
								field: controlField,
								value: controlValue,
							},
						};

						// Form values where the control field has the expected value
						const formValues = { [controlField]: controlValue };

						const result = isFieldVisible(schema, formValues);
						expect(result).toBe(true);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return false when ui_show_if condition is not satisfied", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					primitiveValueArb,
					primitiveValueArb,
					basePropertySchemaArb,
					(controlField, expectedValue, actualValue, baseSchema) => {
						// Skip if values happen to be equal
						fc.pre(actualValue !== expectedValue);

						// Create schema with ui_show_if
						const schema: PropertySchema = {
							...(baseSchema as PropertySchema),
							ui_show_if: {
								field: controlField,
								value: expectedValue,
							},
						};

						// Form values where the control field has a different value
						const formValues = { [controlField]: actualValue };

						const result = isFieldVisible(schema, formValues);
						expect(result).toBe(false);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return false when control field is missing from form values", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					primitiveValueArb,
					basePropertySchemaArb,
					(controlField, expectedValue, baseSchema) => {
						// Create schema with ui_show_if
						const schema: PropertySchema = {
							...(baseSchema as PropertySchema),
							ui_show_if: {
								field: controlField,
								value: expectedValue,
							},
						};

						// Empty form values (control field is missing)
						const formValues: Record<string, unknown> = {};

						const result = isFieldVisible(schema, formValues);
						expect(result).toBe(false);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should support array values in ui_show_if (any match)", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					fc.array(primitiveValueArb, { minLength: 1, maxLength: 5 }),
					basePropertySchemaArb,
					(controlField, allowedValues, baseSchema) => {
						// Pick one of the allowed values
						const actualValue = allowedValues[0];

						// Create schema with ui_show_if using array
						const schema: PropertySchema = {
							...(baseSchema as PropertySchema),
							ui_show_if: {
								field: controlField,
								value: allowedValues,
							},
						};

						// Form values where the control field has one of the allowed values
						const formValues = { [controlField]: actualValue };

						const result = isFieldVisible(schema, formValues);
						expect(result).toBe(true);
					},
				),
				{ numRuns: 100 },
			);
		});

		it("should return false when value not in ui_show_if array", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					fc.array(fc.constantFrom("a", "b", "c"), {
						minLength: 1,
						maxLength: 3,
					}),
					basePropertySchemaArb,
					(controlField, allowedValues, baseSchema) => {
						// Use a value that's definitely not in the array
						const actualValue = "definitely_not_in_array_xyz";

						// Create schema with ui_show_if using array
						const schema: PropertySchema = {
							...(baseSchema as PropertySchema),
							ui_show_if: {
								field: controlField,
								value: allowedValues,
							},
						};

						// Form values where the control field has a value not in the array
						const formValues = { [controlField]: actualValue };

						const result = isFieldVisible(schema, formValues);
						expect(result).toBe(false);
					},
				),
				{ numRuns: 100 },
			);
		});
	});

	describe("DynamicConfigForm component rendering", () => {
		it("should not render fields when ui_show_if condition is not met", () => {
			fc.assert(
				fc.property(
					fieldNameArb,
					fieldNameArb,
					fc.constantFrom("option1", "option2", "option3"),
					(controlFieldName, conditionalFieldName, controlValue) => {
						// Ensure field names are different
						fc.pre(controlFieldName !== conditionalFieldName);

						const schema: ConfigSchema = {
							type: "object",
							properties: {
								[controlFieldName]: {
									type: "string",
									title: "Control Field",
									description: "Controls visibility",
									ui_component: "select",
									enum: ["option1", "option2", "option3"],
								},
								[conditionalFieldName]: {
									type: "string",
									title: "Conditional Field",
									description: "Only visible when control is option1",
									ui_component: "input",
									ui_show_if: {
										field: controlFieldName,
										value: "option1",
									},
								},
							},
						};

						// Set control field to a value that should hide the conditional field
						const formValue = { [controlFieldName]: controlValue };
						const shouldBeVisible = controlValue === "option1";

						const { container } = render(
							<DynamicConfigForm
								schema={schema}
								value={formValue}
								onChange={() => {}}
							/>,
						);

						// Check if conditional field is rendered
						const conditionalFieldLabel = container.querySelector(
							`[data-testid="field-${conditionalFieldName}"]`,
						);

						if (shouldBeVisible) {
							expect(conditionalFieldLabel).not.toBeNull();
						} else {
							expect(conditionalFieldLabel).toBeNull();
						}
					},
				),
				{ numRuns: 50 },
			);
		});

		it("should render fields when ui_show_if condition is met", () => {
			const schema: ConfigSchema = {
				type: "object",
				properties: {
					mode: {
						type: "string",
						title: "Mode",
						description: "Select mode",
						ui_component: "select",
						enum: ["simple", "advanced"],
					},
					advancedOption: {
						type: "string",
						title: "Advanced Option",
						description: "Only visible in advanced mode",
						ui_component: "input",
						ui_show_if: {
							field: "mode",
							value: "advanced",
						},
					},
				},
			};

			// When mode is "advanced", the advancedOption field should be visible
			const { container, rerender } = render(
				<DynamicConfigForm
					schema={schema}
					value={{ mode: "advanced" }}
					onChange={() => {}}
				/>,
			);

			// Should be visible
			expect(
				container.querySelector('[data-testid="field-advancedOption"]'),
			).not.toBeNull();

			// When mode is "simple", the advancedOption field should be hidden
			rerender(
				<DynamicConfigForm
					schema={schema}
					value={{ mode: "simple" }}
					onChange={() => {}}
				/>,
			);

			// Should be hidden
			expect(
				container.querySelector('[data-testid="field-advancedOption"]'),
			).toBeNull();
		});
	});
});
