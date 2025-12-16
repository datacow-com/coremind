/**
 * DynamicConfigForm Utilities
 *
 * Utility functions for form validation and field visibility
 */

import type { ConfigSchema, PropertySchema } from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface ValidationError {
	field: string;
	message: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Conditional Visibility Logic
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Check if a field should be visible based on ui_show_if condition
 *
 * Requirements: 7.5
 */
export function isFieldVisible(
	schema: PropertySchema,
	formValues: Record<string, unknown>,
): boolean {
	if (!schema.ui_show_if) {
		return true;
	}

	const { field, value: expectedValue } = schema.ui_show_if;
	const actualValue = formValues[field];

	// Handle array comparison
	if (Array.isArray(expectedValue)) {
		return expectedValue.includes(actualValue);
	}

	// Direct value comparison
	return actualValue === expectedValue;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Validation Logic
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Validate form values against schema
 *
 * Requirements: 7.6
 */
export function validateForm(
	schema: ConfigSchema,
	values: Record<string, unknown>,
): ValidationError[] {
	const errors: ValidationError[] = [];
	const { properties, required = [] } = schema;

	for (const [fieldName, fieldSchema] of Object.entries(properties)) {
		const value = values[fieldName];

		// Skip validation for hidden fields
		if (!isFieldVisible(fieldSchema, values)) {
			continue;
		}

		// Required field validation
		if (required.includes(fieldName)) {
			if (value === undefined || value === null || value === "") {
				errors.push({
					field: fieldName,
					message: `${fieldSchema.title || fieldName} is required`,
				});
				continue;
			}
		}

		// Skip further validation if value is empty and not required
		if (value === undefined || value === null) {
			continue;
		}

		// Type-specific validation
		if (fieldSchema.type === "number" || fieldSchema.type === "integer") {
			const numValue = Number(value);
			if (isNaN(numValue)) {
				errors.push({
					field: fieldName,
					message: `${fieldSchema.title || fieldName} must be a number`,
				});
			} else {
				if (
					fieldSchema.minimum !== undefined &&
					numValue < fieldSchema.minimum
				) {
					errors.push({
						field: fieldName,
						message: `${fieldSchema.title || fieldName} must be at least ${fieldSchema.minimum}`,
					});
				}
				if (
					fieldSchema.maximum !== undefined &&
					numValue > fieldSchema.maximum
				) {
					errors.push({
						field: fieldName,
						message: `${fieldSchema.title || fieldName} must be at most ${fieldSchema.maximum}`,
					});
				}
			}
		}

		// Enum validation
		if (fieldSchema.enum && !fieldSchema.enum.includes(String(value))) {
			errors.push({
				field: fieldName,
				message: `${fieldSchema.title || fieldName} must be one of: ${fieldSchema.enum.join(", ")}`,
			});
		}
	}

	return errors;
}
