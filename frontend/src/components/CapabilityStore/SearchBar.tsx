/**
 * SearchBar - 能力搜索栏组件
 *
 * 提供能力搜索功能，支持按名称和描述搜索
 *
 * Requirements: 5.5
 */

import { Search, X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface SearchBarProps {
	/** Current search query */
	value: string;
	/** Callback when search query changes */
	onChange: (value: string) => void;
	/** Placeholder text */
	placeholder?: string;
	/** Additional CSS classes */
	className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

export const SearchBar: React.FC<SearchBarProps> = ({
	value,
	onChange,
	placeholder = "搜索能力...",
	className,
}) => {
	const inputRef = React.useRef<HTMLInputElement>(null);

	const handleClear = () => {
		onChange("");
		inputRef.current?.focus();
	};

	return (
		<div
			className={cn(
				"flex items-center border rounded-md px-3 py-1.5 bg-gray-50 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500",
				className,
			)}
		>
			<Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
			<input
				ref={inputRef}
				type="text"
				value={value}
				onChange={(e) => onChange(e.target.value)}
				placeholder={placeholder}
				className="px-2 py-0.5 text-sm outline-none bg-transparent flex-1 min-w-0"
				data-testid="capability-search-input"
			/>
			{value && (
				<button
					onClick={handleClear}
					className="p-0.5 hover:bg-gray-200 rounded"
					aria-label="清除搜索"
				>
					<X className="h-4 w-4 text-gray-400" />
				</button>
			)}
		</div>
	);
};

export default SearchBar;
