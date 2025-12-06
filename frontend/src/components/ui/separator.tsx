import * as React from "react";
import { cn } from "@/lib/utils";

export const Separator: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => <div className={cn("h-px w-full bg-gray-200", className)} {...props} />;
