const DEFAULT_MAX_BYTES = 50 * 1024 * 1024; // 50MB 前端保护

export type FileCheck = {
  ok: boolean;
  error?: string;
};

export const checkFile = (
  file: File,
  opts: { exts?: string[]; maxBytes?: number } = {},
): FileCheck => {
  const { exts, maxBytes = DEFAULT_MAX_BYTES } = opts;
  if (maxBytes && file.size > maxBytes) {
    return {
      ok: false,
      error: `文件过大，最大 ${Math.round(maxBytes / 1024 / 1024)}MB`,
    };
  }
  if (exts && exts.length > 0) {
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (!ext || !exts.map((x) => x.toLowerCase()).includes(ext)) {
      return {
        ok: false,
        error: `不支持的文件类型，仅允许: ${exts.join(", ")}`,
      };
    }
  }
  return { ok: true };
};
