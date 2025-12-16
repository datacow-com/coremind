/**
 * NumberField - Numeric input component
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import type * as React from "react";
import { Input } from "@/components/ui/input";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const NumberField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	const min = schema.minimum;
	const max = schema.maximum;
	const step = schema.ui_step ?? 1;

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const rawValue = e.target.value;

		// Allow empty string for clearing
		if (rawValue === "") {
			onChange(undefined);
			return;
		}

		const numValue = parseFloat(rawValue);
		if (!isNaN(numValue)) {
			onChange(numValue);
		}
	};

	// Handle blur to enforce min/max
	const handleBlur = () => {
		if (typeof value !== "number") return;

		let clampedValue = value;
		if (min !== undefined && value < min) {
			clampedValue = min;
		}
		if (max !== undefined && value > max) {
			clampedValue = max;
		}

		if (clampedValue !== value) {
			onChange(clampedValue);
		}
	};

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<Input
				type="number"
				id={name}
				name={name}
				value={value !== undefined ? String(value) : ""}
				onChange={handleChange}
				onBlur={handleBlur}
				disabled={disabled}
				min={min}
				max={max}
				step={step}
				data-testid={`number-field-${name}`}
			/>
			{(min !== undefined || max !== undefined) && (
				<p className="text-xs text-muted-foreground">
					{min !== undefined && max !== undefined
						? `Range: ${min} - ${max}`
						: min !== undefined
							? `Min: ${min}`
							: `Max: ${max}`}
				</p>
			)}
		</FieldWrapper>
	);
};

export default NumberField;
