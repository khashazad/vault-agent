import { test, expect } from "@playwright/test";
import { mockApi } from "../mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("navigate to Changesets page and see changeset list", async ({ page }) => {
  await page.goto("/changesets");
  await expect(page.getByText("Changeset History")).toBeVisible();
  await expect(page.getByTestId("delete-cshist01-abcd-1234")).toBeVisible();
  await expect(page.getByTestId("delete-cshist02-efgh-5678")).toBeVisible();
});

test("status filter tabs are visible", async ({ page }) => {
  await page.goto("/changesets");
  await expect(page.getByRole("button", { name: "All", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pending", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Applied", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rejected", exact: true })).toBeVisible();
});

test("click changeset card to see detail", async ({ page }) => {
  await page.goto("/changesets");
  await expect(page.getByTestId("delete-cshist01-abcd-1234")).toBeVisible();

  // Click first changeset card
  const card = page.getByTestId("delete-cshist01-abcd-1234").locator("xpath=ancestor::div[@role='button']");
  await card.click();
  await expect(page.getByText("Changeset Detail")).toBeVisible();
});

test("back button returns to list from detail", async ({ page }) => {
  await page.goto("/changesets");
  const card = page.getByTestId("delete-cshist01-abcd-1234").locator("xpath=ancestor::div[@role='button']");
  await card.click();
  await expect(page.getByText("Changeset Detail")).toBeVisible();

  // Click back
  await page.getByTitle("Back to list").click();
  await expect(page.getByText("Changeset History")).toBeVisible();
});

test("delete button shows popover and sends DELETE request", async ({ page }) => {
  await page.goto("/changesets");
  await expect(page.getByTestId("delete-cshist01-abcd-1234")).toBeVisible();

  await page.getByTestId("delete-cshist01-abcd-1234").click();
  await expect(page.getByTestId("delete-confirm-popover")).toBeVisible();

  const deletePromise = page.waitForRequest(
    (req) => req.method() === "DELETE" && req.url().includes("/changesets/"),
  );
  await page.getByTestId("confirm-delete-btn").click();
  const req = await deletePromise;
  expect(req.method()).toBe("DELETE");
});

test("sidebar navigation between Library and Changesets", async ({ page }) => {
  await page.goto("/changesets");
  await expect(page.getByText("Changeset History")).toBeVisible();

  // Click Library in sidebar
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page.getByText("Zotero Library")).toBeVisible();
});
