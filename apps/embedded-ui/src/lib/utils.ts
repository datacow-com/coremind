export function cn(
  ...inputs: Array<string | number | null | undefined | boolean>
) {
  return inputs.filter(Boolean).join(" ");
}
