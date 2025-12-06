import { useEffect, useRef } from "react";

export const useDebouncedEffect = (
  fn: () => void,
  deps: any[],
  delay = 400,
) => {
  const timer = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(), delay);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
};
