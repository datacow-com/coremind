/**
 * TextField - Multi-line text input component
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import type * as React from "react";
import { cn } from "@/lib/utils";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const TextField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
		onChange(e.target.value);
	};

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<textarea
				id={name}
				name={name}
				value={String(value ?? "")}
				onChange={handleChange}
				disabled={disabled}
				rows={4}
				data-testid={`text-field-${name}`}
				className={cn(
					"w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground",
					"focus:outline-none focus:ring-2 focus:ring-primary",
					"resize-y min-h-[80px]",
					disabled && "opacity-50 cursor-not-allowed",
				)}
			/>
		</FieldWrapper>
	);
};

export default TextField;
