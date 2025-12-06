import { cn } from "@/lib/theme";

export const SkeletonBlock: React.FC<{ className?: string }> = ({
  className,
}) => (
  <div className={cn("animate-pulse rounded-md bg-gray-200/80", className)} />
);
