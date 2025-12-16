/**
 * SliderField - Range slider component for numeric values
 *
 * Requirements: 7.2
 */

import type * as React from "react";
import { cn } from "@/lib/utils";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const SliderField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	const min = schema.minimum ?? 0;
	const max = schema.maximum ?? 100;
	const step = schema.ui_step ?? 1;
	const currentValue = typeof value === "number" ? value : min;

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const numValue = parseFloat(e.target.value);
		onChange(numValue);
	};

	// Calculate percentage for gradient background
	const percentage = ((currentValue - min) / (max - min)) * 100;

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<div className="flex items-center gap-4">
				<input
					type="range"
					id={name}
					name={name}
					min={min}
					max={max}
					step={step}
					value={currentValue}
					onChange={handleChange}
					disabled={disabled}
					data-testid={`slider-field-${name}`}
					className={cn(
						"w-full h-2 rounded-lg appearance-none cursor-pointer",
						"bg-input",
						"[&::-webkit-slider-thumb]:appearance-none",
						"[&::-webkit-slider-thumb]:w-4",
						"[&::-webkit-slider-thumb]:h-4",
						"[&::-webkit-slider-thumb]:rounded-full",
						"[&::-webkit-slider-thumb]:bg-primary",
						"[&::-webkit-slider-thumb]:cursor-pointer",
						"[&::-moz-range-thumb]:w-4",
						"[&::-moz-range-thumb]:h-4",
						"[&::-moz-range-thumb]:rounded-full",
						"[&::-moz-range-thumb]:bg-primary",
						"[&::-moz-range-thumb]:cursor-pointer",
						"[&::-moz-range-thumb]:border-0",
						disabled && "opacity-50 cursor-not-allowed",
					)}
					style={{
						background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${percentage}%, hsl(var(--input)) ${percentage}%, hsl(var(--input)) 100%)`,
					}}
				/>
				<span className="min-w-[3rem] text-sm text-muted-foreground text-right">
					{currentValue}
				</span>
			</div>
			<div className="flex justify-between text-xs text-muted-foreground">
				<span>{min}</span>
				<span>{max}</span>
			</div>
		</FieldWrapper>
	);
};

export default SliderField;
