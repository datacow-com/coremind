/**
 * DynamicConfigForm - 动态配置表单组件
 *
 * 根据 config_schema 动态生成配置表单，支持多种字段类型和条件显示
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
 */

import * as React from "react";
import { cn } from "@/lib/utils";

import { getFieldComponent } from "./componentMap";
import type {
	DynamicConfigFormProps,
	FieldProps,
	ValidationError,
} from "./types";
import { isFieldVisible, validateForm } from "./utils";

// Re-export types and utilities for external use
export type { DynamicConfigFormProps, ValidationError, FieldProps };
export { componentMap, getFieldComponent } from "./componentMap";
export { isFieldVisible, validateForm } from "./utils";

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * DynamicConfigForm - Renders a form based on config_schema
 */
export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
	schema,
	value,
	onChange,
	onValidate,
	className,
	disabled = false,
	errors = [],
}) => {
	// Create error lookup map
	const errorMap = React.useMemo(() => {
		const map: Record<string, string> = {};
		for (const error of errors) {
			map[error.field] = error.message;
		}
		return map;
	}, [errors]);

	// Handle field value change
	const handleFieldChange = React.useCallback(
		(fieldName: string, fieldValue: unknown) => {
			const newValues = { ...value, [fieldName]: fieldValue };
			onChange(newValues);

			// Trigger validation if callback provided
			if (onValidate) {
				const validationErrors = validateForm(schema, newValues);
				onValidate(validationErrors);
			}
		},
		[value, onChange, onValidate, schema],
	);

	// Get sorted field entries (maintain order from schema)
	const fieldEntries = React.useMemo(() => {
		return Object.entries(schema.properties);
	}, [schema.properties]);

	return (
		<div
			className={cn("space-y-4", className)}
			data-testid="dynamic-config-form"
		>
			{fieldEntries.map(([fieldName, fieldSchema]) => {
				// Check visibility condition
				if (!isFieldVisible(fieldSchema, value)) {
					return null;
				}

				// Get the appropriate component
				const FieldComponent = getFieldComponent(fieldSchema);
				if (!FieldComponent) {
					console.warn(
						`Unknown ui_component type: ${fieldSchema.ui_component} for field ${fieldName}`,
					);
					return null;
				}

				// Get current field value, falling back to default
				const fieldValue =
					value[fieldName] !== undefined
						? value[fieldName]
						: fieldSchema.default;

				return (
					<FieldComponent
						key={fieldName}
						name={fieldName}
						schema={fieldSchema}
						value={fieldValue}
						onChange={(newValue) => handleFieldChange(fieldName, newValue)}
						disabled={disabled}
						error={errorMap[fieldName]}
					/>
				);
			})}
		</div>
	);
};

export default DynamicConfigForm;
