/**
 * InputField - Single-line text input component
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import type * as React from "react";
import { Input } from "@/components/ui/input";
import type { FieldProps } from "../types";
import { FieldWrapper } from "./FieldWrapper";

export const InputField: React.FC<FieldProps> = ({
	name,
	schema,
	value,
	onChange,
	disabled,
	error,
}) => {
	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		onChange(e.target.value);
	};

	return (
		<FieldWrapper name={name} schema={schema} error={error}>
			<Input
				type="text"
				id={name}
				name={name}
				value={String(value ?? "")}
				onChange={handleChange}
				disabled={disabled}
				data-testid={`input-field-${name}`}
			/>
		</FieldWrapper>
	);
};

export default InputField;
