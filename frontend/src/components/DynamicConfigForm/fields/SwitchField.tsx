/**
 * SwitchField - Toggle switch component for boolean values
 *
 * Requirements: 7.3
 */

import type * as React from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { FieldProps } from "../types";

export const SwitchField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	const isChecked = Boolean(value);

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		onChange(e.target.checked);
	};

	return (
		<div className="space-y-2">
			<div className="flex items-center justify-between">
				<div className="space-y-1">
					<Label htmlFor={name}>{schema.title || name}</Label>
					{schema.description && (
						<p className="text-xs text-muted-foreground">
							{schema.description}
						</p>
					)}
				</div>
				<label className="inline-flex cursor-pointer items-center">
					<input
						type="checkbox"
						id={name}
						name={name}
						checked={isChecked}
						onChange={handleChange}
						disabled={disabled}
						data-testid={`switch-field-${name}`}
						className="peer sr-only"
					/>
					<span
						className={cn(
							"relative h-6 w-11 rounded-full transition-colors",
							"bg-input peer-checked:bg-primary",
							"after:absolute after:left-[2px] after:top-[2px]",
							"after:h-5 after:w-5 after:rounded-full after:bg-white",
							"after:transition-all after:content-['']",
							"peer-checked:after:translate-x-5",
							disabled && "opacity-50 cursor-not-allowed",
						)}
					/>
				</label>
			</div>
			{error && <p className="text-xs text-destructive">{error}</p>}
		</div>
	);
};

export default SwitchField;
