import { useState, useCallback } from "react";
import {
  ToastProvider as RadixToastProvider,
  ToastViewport,
  Toast,
  ToastTitle,
  ToastDescription,
  ToastClose,
} from "./toast";

type ToastItem = {
  id: number;
  title: string;
  description?: string;
  variant?: "default" | "error" | "success";
};

let seed = 1;

export const useToast = () => {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((item: Omit<ToastItem, "id">) => {
    const id = seed++;
    setItems((prev) => [...prev, { ...item, id }]);
  }, []);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const portal = (
    <RadixToastProvider swipeDirection="right">
      {items.map((t) => (
        <Toast
          key={t.id}
          className={
            t.variant === "error"
              ? "border-red-200 bg-red-50"
              : t.variant === "success"
                ? "border-green-200 bg-green-50"
                : undefined
          }
          onOpenChange={(open) => {
            if (!open) remove(t.id);
          }}
        >
          <ToastTitle>{t.title}</ToastTitle>
          {t.description && (
            <ToastDescription>{t.description}</ToastDescription>
          )}
          <ToastClose>×</ToastClose>
        </Toast>
      ))}
      <ToastViewport />
    </RadixToastProvider>
  );

  return { push, remove, portal };
};
