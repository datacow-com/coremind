import * as React from "react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

export interface Option {
  label: string;
  value: string;
}
export interface SelectSearchProps {
  options: Option[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export const SelectSearch: React.FC<SelectSearchProps> = ({
  options,
  value,
  onChange,
  placeholder,
  className,
}) => {
  const [q, setQ] = React.useState("");
  const t = q.toLowerCase();
  const filtered = options.filter(
    (o) =>
      o.label.toLowerCase().includes(t) || o.value.toLowerCase().includes(t),
  );
  const listId = React.useId();
  return (
    <div className={cn("space-y-2", className)}>
      <Input
        list={listId}
        value={value ?? ""}
        onChange={(e) => onChange?.(e.target.value)}
        onInput={(e) => setQ((e.target as HTMLInputElement).value)}
        placeholder={placeholder || "搜索模型..."}
      />
      <datalist id={listId}>
        {filtered.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </datalist>
    </div>
  );
};
