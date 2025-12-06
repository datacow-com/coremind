import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/theme";

type Variant = "info" | "success" | "error";

const iconMap: Record<Variant, JSX.Element> = {
  info: <Info className="h-4 w-4 text-blue-600" />,
  success: <CheckCircle2 className="h-4 w-4 text-green-600" />,
  error: <AlertTriangle className="h-4 w-4 text-red-600" />,
};

const bgMap: Record<Variant, string> = {
  info: "bg-blue-50 border-blue-100 text-blue-800",
  success: "bg-green-50 border-green-100 text-green-800",
  error: "bg-red-50 border-red-100 text-red-800",
};

export const AlertCard: React.FC<{
  title: string;
  description?: string;
  variant?: Variant;
  className?: string;
}> = ({ title, description, variant = "info", className }) => (
  <div
    className={cn(
      "flex items-start space-x-2 rounded-md border p-3 text-sm",
      bgMap[variant],
      className,
    )}
  >
    <div className="mt-0.5">{iconMap[variant]}</div>
    <div>
      <div className="font-medium">{title}</div>
      {description && <div className="text-xs mt-1 opacity-80">{description}</div>}
    </div>
  </div>
);
