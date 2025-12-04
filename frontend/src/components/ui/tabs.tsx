import * as React from "react";
import { cn } from "@/lib/utils";

export const Tabs: React.FC<{
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children?: React.ReactNode;
}> = ({ value, className, children }) => {
  return (
    <div className={cn("", className)} data-value={value}>
      {children}
    </div>
  );
};

export const TabsList: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => <div className={cn("flex space-x-2 border-b", className)} {...props} />;

export const TabsTrigger: React.FC<{
  value?: string;
  active?: boolean;
  onClick?: () => void;
  children?: React.ReactNode;
}> = ({ active, onClick, children }) => (
  <button
    onClick={onClick}
    className={cn(
      "px-3 py-2 text-sm",
      active
        ? "border-b-2 border-blue-600 text-blue-700"
        : "text-gray-600 hover:text-gray-900",
    )}
  >
    {children}
  </button>
);

export const TabsContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => <div className={cn("py-4", className)} {...props} />;
