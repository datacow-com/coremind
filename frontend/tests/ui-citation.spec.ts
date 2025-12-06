import { test, expect } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { PDFDocument, StandardFonts } from "pdf-lib";

const BASE = process.env.UI_BASE_URL || "http://localhost:3500";

async function createTempPdf(): Promise<string> {
  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([595, 842]);
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);
  page.drawText("Citation E2E", { x: 72, y: 770, size: 18, font });
  // draw simple table
  page.drawLine({ start: { x: 70, y: 200 }, end: { x: 500, y: 200 } });
  page.drawLine({ start: { x: 70, y: 240 }, end: { x: 500, y: 240 } });
  page.drawLine({ start: { x: 70, y: 200 }, end: { x: 70, y: 240 } });
  page.drawLine({ start: { x: 500, y: 200 }, end: { x: 500, y: 240 } });
  const bytes = await pdfDoc.save();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "omnirag-"));
  const file = path.join(tmp, "e2e-citation.pdf");
  fs.writeFileSync(file, bytes);
  return file;
}

test("upload PDF and show citation preview", async ({ page }) => {
  const file = await createTempPdf();
  await page.goto(BASE + "/");
  const pdfInput = page.locator('input[type="file"][accept=".pdf"]');
  await pdfInput.setInputFiles(file);
  // wait for document to appear in dropdown
  await expect(page.locator("select").first()).toContainText(
    "e2e-citation.pdf",
  );

  // ask a question
  await page.fill("textarea", "Show table content on page 1");
  await page.click('button:has-text("Send")');

  // wait for sources to render and click first
  await expect(page.locator("text=Sources:")).toBeVisible({ timeout: 20000 });
  await page.click('button:has-text("[1]")');

  // preview should be visible with overlay boxes
  await expect(page.locator('img[alt="preview"]')).toBeVisible();
  const overlays = page.locator('div[style*="position: absolute"]');
  await expect(overlays).toHaveCountGreaterThan(0);
});
