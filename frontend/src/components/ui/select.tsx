import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(({ className, children, ...props }, ref) => {
  return (
    <select
      ref={ref}
      className={cn("w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground", className)}
      {...props}
    >
      {children}
    </select>
  );
});
Select.displayName = "Select";
