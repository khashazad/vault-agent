import { test, expect } from "@playwright/test";
import { mockApi } from "../mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("navigate to History tab and see changeset list", async ({ page }) => {
  await page.goto("/");
  await page.getByText("History").click();
  await expect(page.getByText("Changeset History")).toBeVisible();
  await expect(page.getByText(/cshist01/)).toBeVisible();
  await expect(page.getByText(/cshist02/)).toBeVisible();
});

test("status filter tabs are visible", async ({ page }) => {
  await page.goto("/");
  await page.getByText("History").click();
  await expect(page.getByRole("button", { name: "All", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pending", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Applied", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rejected", exact: true })).toBeVisible();
});

test("click changeset card to see detail", async ({ page }) => {
  await page.goto("/");
  await page.getByText("History").click();
  await expect(page.getByText(/cshist01/)).toBeVisible();

  // Click first changeset card
  await page.getByText(/cshist01/).click();
  await expect(page.getByText("Changeset Detail")).toBeVisible();
});

test("back button returns to list from detail", async ({ page }) => {
  await page.goto("/");
  await page.getByText("History").click();
  await page.getByText(/cshist01/).click();
  await expect(page.getByText("Changeset Detail")).toBeVisible();

  // Click back
  await page.getByTitle("Back to list").click();
  await expect(page.getByText("Changeset History")).toBeVisible();
});

test("Sync tab still works after visiting History", async ({ page }) => {
  await page.goto("/");
  await page.getByText("History").click();
  await expect(page.getByText("Changeset History")).toBeVisible();

  // Switch back to Sync
  await page.getByText("Sync").click();
  await expect(page.getByText("Zotero Library")).toBeVisible();
});
