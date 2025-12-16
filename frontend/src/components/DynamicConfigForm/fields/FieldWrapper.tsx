/**
 * FieldWrapper - Common wrapper for form fields
 *
 * Provides consistent layout for label, description, field, and error display
 */

import type * as React from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { PropertySchema } from "@/store/capabilityStore";

export interface FieldWrapperProps {
	/** Field name */
	name: string;
	/** Property schema */
	schema: PropertySchema;
	/** Error message */
	error?: string;
	/** Whether field is required */
	required?: boolean;
	/** Children (the actual field input) */
	children: React.ReactNode;
	/** Additional CSS classes */
	className?: string;
}

export const FieldWrapper: React.FC<FieldWrapperProps> = ({
	name,
	schema,
	error,
	required,
	children,
	className,
}) => {
	return (
		<div className={cn("space-y-2", className)} data-testid={`field-${name}`}>
			<div className="flex items-center justify-between">
				<Label htmlFor={name} requiredMark={required}>
					{schema.title || name}
				</Label>
			</div>
			{schema.description && (
				<p className="text-xs text-muted-foreground">{schema.description}</p>
			)}
			{children}
			{error && <p className="text-xs text-destructive">{error}</p>}
		</div>
	);
};

export default FieldWrapper;
