import { test, expect } from "@playwright/test";

const BASE = process.env.UI_BASE_URL || "http://localhost:3500";

test("root page loads", async ({ page }) => {
  await page.goto(BASE + "/");
  await expect(page).toHaveTitle(/OmniRAG/i);
});

test("backend health ok", async ({ request }) => {
  const res = await request.get(BASE + "/api/health");
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.app_up).toBeTruthy();
});
