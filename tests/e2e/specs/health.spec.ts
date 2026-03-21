import { test, expect } from "@playwright/test";
import { mockApi } from "../mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("page loads with sidebar and branding visible", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("aside")).toBeVisible();
  await expect(page.getByText("Vault Agent")).toBeVisible();
});

test("Zotero Library heading appears when configured", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Zotero Library")).toBeVisible();
});

test("shows not-configured message when Zotero is disabled", async ({
  page,
}) => {
  // Override status to unconfigured
  await page.route("**/zotero/status", (route) =>
    route.fulfill({
      json: { configured: false, last_version: null, last_synced: null },
    })
  );
  await page.goto("/");
  await expect(page.getByText("Zotero is not configured")).toBeVisible();
});
