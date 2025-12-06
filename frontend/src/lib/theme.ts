import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: Array<string | undefined | null | false>) {
  return twMerge(clsx(inputs));
}

export const tokens = {
  radius: {
    sm: "0.25rem",
    md: "0.375rem",
    lg: "0.5rem",
  },
  shadow: {
    card: "0 2px 8px rgba(0,0,0,0.06)",
  },
};
