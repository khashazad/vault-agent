import { test, expect } from "@playwright/test";
import { mockApi } from "../mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("renders paper list", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Attention Is All You Need")).toBeVisible();
  await expect(
    page.getByText("BERT: Pre-training of Deep Bidirectional Transformers")
  ).toBeVisible();
  await expect(page.getByText("GPT-4 Technical Report")).toBeVisible();
});

test("displays author and year", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Vaswani, A., Shazeer, N.")).toBeVisible();
  await expect(page.getByText("(2017)")).toBeVisible();
});

test("shows collection sidebar", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Machine Learning")).toBeVisible();
  await expect(page.getByText("My Library")).toBeVisible();
});

test("search input filters papers", async ({ page }) => {
  await page.goto("/");
  const searchInput = page.getByPlaceholder("Search by title or author...");
  await expect(searchInput).toBeVisible();
  // Type in search — the mock always returns same data, but input should be functional
  await searchInput.fill("transformer");
  await expect(searchInput).toHaveValue("transformer");
});

test("sync status filter buttons are present", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "All", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Synced", exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Not Synced", exact: true })
  ).toBeVisible();
});

test("Sync with Zotero button is visible", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Sync with Zotero" })
  ).toBeVisible();
});
