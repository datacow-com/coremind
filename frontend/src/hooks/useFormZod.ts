import { useState } from "react";
import { ZodSchema, ZodError } from "zod";

type SubmitHandler<T> = (data: T) => Promise<void> | void;

export const useFormZod = <T>(
  schema: ZodSchema<T>,
  initial: T,
  onSubmit: SubmitHandler<T>,
) => {
  const [values, setValues] = useState<T>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof T>(key: K, value: T[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const submit = async () => {
    try {
      setSubmitting(true);
      const parsed = schema.parse(values);
      await onSubmit(parsed);
    } catch (e) {
      if (e instanceof ZodError) {
        const next: Partial<Record<keyof T, string>> = {};
        e.errors.forEach((err) => {
          const path = err.path[0] as keyof T;
          next[path] = err.message;
        });
        setErrors(next);
      } else {
        throw e;
      }
    } finally {
      setSubmitting(false);
    }
  };

  return {
    values,
    errors,
    submitting,
    setField,
    submit,
    setValues,
  };
};
