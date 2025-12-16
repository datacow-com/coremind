/**
 * Component Map for DynamicConfigForm
 *
 * Maps ui_component types to field components
 */

import type { PropertySchema } from "@/store/capabilityStore";
import { InputField } from "./fields/InputField";
import { MultiSelectField } from "./fields/MultiSelectField";
import { NumberField } from "./fields/NumberField";
import { SelectField } from "./fields/SelectField";
import { SliderField } from "./fields/SliderField";
import { SwitchField } from "./fields/SwitchField";
import { TextField } from "./fields/TextField";
import type { FieldProps } from "./types";

// ═══════════════════════════════════════════════════════════════════════════════
// Component Mapping
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Maps ui_component types to field components
 */
export const componentMap: Record<string, React.ComponentType<FieldProps>> = {
	select: SelectField,
	slider: SliderField,
	switch: SwitchField,
	"multi-select": MultiSelectField,
	number: NumberField,
	text: TextField,
	input: InputField,
};

/**
 * Get the appropriate field component for a schema property
 */
export function getFieldComponent(
	schema: PropertySchema,
): React.ComponentType<FieldProps> | null {
	const componentType = schema.ui_component;
	return componentMap[componentType] || null;
}
