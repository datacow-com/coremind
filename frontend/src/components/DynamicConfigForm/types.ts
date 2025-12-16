/**
 * Types for DynamicConfigForm
 */

import type { ConfigSchema, PropertySchema } from "@/store/capabilityStore";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface ValidationError {
	field: string;
	message: string;
}

export interface DynamicConfigFormProps {
	/** Config schema defining the form structure */
	schema: ConfigSchema;
	/** Current form values */
	value: Record<string, unknown>;
	/** Callback when values change */
	onChange: (value: Record<string, unknown>) => void;
	/** Optional validation callback */
	onValidate?: (errors: ValidationError[]) => void;
	/** Additional CSS classes */
	className?: string;
	/** Whether the form is disabled */
	disabled?: boolean;
	/** Validation errors to display */
	errors?: ValidationError[];
}

export interface FieldProps {
	/** Field name/key */
	name: string;
	/** Property schema */
	schema: PropertySchema;
	/** Current value */
	value: unknown;
	/** Change handler */
	onChange: (value: unknown) => void;
	/** Whether field is disabled */
	disabled?: boolean;
	/** Validation error message */
	error?: string;
}
