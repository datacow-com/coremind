/**
 * SelectField - Dropdown select component for enum values
 *
 * Requirements: 7.1
 */

import * as React from "react";
import { Select } from "@/components/ui/select";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const SelectField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	// Get options from enum or available_options
	const options = React.useMemo(() => {
		if (schema.available_options) {
			return schema.available_options;
		}
		if (schema.enum) {
			return schema.enum.map((val) => ({
				value: val,
				label: schema.enum_labels?.[val] || val,
			}));
		}
		return [];
	}, [schema.enum, schema.enum_labels, schema.available_options]);

	const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		onChange(e.target.value);
	};

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<Select
				id={name}
				name={name}
				value={String(value ?? "")}
				onChange={handleChange}
				disabled={disabled}
				data-testid={`select-field-${name}`}
			>
				<option value="">Select...</option>
				{options.map((opt) => (
					<option key={opt.value} value={opt.value}>
						{opt.label}
					</option>
				))}
			</Select>
		</FieldWrapper>
	);
};

export default SelectField;
