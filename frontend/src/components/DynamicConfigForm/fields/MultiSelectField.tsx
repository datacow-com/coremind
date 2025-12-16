/**
 * MultiSelectField - Multi-select component for array values
 *
 * Requirements: 7.4
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const MultiSelectField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	// Ensure value is an array
	const selectedValues = Array.isArray(value) ? value : [];

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

	const handleToggle = (optionValue: string) => {
		if (disabled) return;

		const newValues = selectedValues.includes(optionValue)
			? selectedValues.filter((v) => v !== optionValue)
			: [...selectedValues, optionValue];

		onChange(newValues);
	};

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<div
				className="flex flex-wrap gap-2"
				data-testid={`multi-select-field-${name}`}
			>
				{options.map((opt) => {
					const isSelected = selectedValues.includes(opt.value);
					return (
						<button
							key={opt.value}
							type="button"
							onClick={() => handleToggle(opt.value)}
							disabled={disabled}
							className={cn(
								"px-3 py-1.5 text-sm rounded-md border transition-colors",
								isSelected
									? "bg-primary text-primary-foreground border-primary"
									: "bg-background text-foreground border-input hover:bg-accent",
								disabled && "opacity-50 cursor-not-allowed",
							)}
						>
							{opt.label}
						</button>
					);
				})}
			</div>
			{selectedValues.length > 0 && (
				<p className="text-xs text-muted-foreground mt-1">
					Selected: {selectedValues.length}
				</p>
			)}
		</FieldWrapper>
	);
};

export default MultiSelectField;
