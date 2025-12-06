import { cn } from "@/lib/theme";
import { FileText } from "lucide-react";

type Props = {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
};

export const EmptyState: React.FC<Props> = ({
  title,
  description,
  icon,
  className,
}) => {
  return (
    <div className={cn("text-center text-gray-500 py-10", className)}>
      <div className="flex justify-center mb-4 text-gray-300">
        {icon || <FileText className="h-14 w-14" />}
      </div>
      <h3 className="text-lg font-medium mb-2 text-gray-700">{title}</h3>
      {description && <p className="text-sm">{description}</p>}
    </div>
  );
};
