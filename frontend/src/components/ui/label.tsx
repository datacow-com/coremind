import * as React from "react";
import { cn } from "@/lib/utils";

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  requiredMark?: boolean;
}

export const Label: React.FC<LabelProps> = ({ className, requiredMark, children, ...props }) => (
  <label className={cn("text-sm text-muted-foreground", className)} {...props}>
    {children}
    {requiredMark ? <span className="ml-1 text-destructive">*</span> : null}
  </label>
);
