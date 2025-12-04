import * as React from "react";
import { cn } from "@/lib/utils";

export interface Option { label: string; value: string }
export interface SelectSearchProps {
  options: Option[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export const SelectSearch: React.FC<SelectSearchProps> = ({ options, value, onChange, placeholder, className }) => {
  const [q, setQ] = React.useState("");
  const filtered = React.useMemo(() => {
    const t = q.toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(t) || o.value.toLowerCase().includes(t));
  }, [q, options]);
  const listId = React.useMemo(() => `select-search-${Math.random().toString(36).slice(2)}`,[options]);
  return (
    <div className={cn("space-y-2", className)}>
      <input
        list={listId}
        className="w-full rounded-md border border-gray-300 bg-white px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        value={value ?? ""}
        onChange={(e)=> onChange?.(e.target.value)}
        onInput={(e)=> setQ((e.target as HTMLInputElement).value)}
        placeholder={placeholder || "搜索模型..."}
      />
      <datalist id={listId}>
        {filtered.map((o)=> (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </datalist>
    </div>
  );
};
