import { test, expect } from "@playwright/test";
import { mockApi } from "../mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("full sync flow: paper → annotations → process → review", async ({
  page,
}) => {
  await page.goto("/");

  // Step 1: Click a paper
  await page.getByText("Attention Is All You Need").click();

  // Step 2: Annotations view loads
  await expect(
    page.getByText("2 of 2 selected")
  ).toBeVisible();

  // Verify annotation text is shown
  await expect(
    page.getByText(/dominant sequence transduction/)
  ).toBeVisible();
  await expect(
    page.getByText(/simple network architecture/)
  ).toBeVisible();

  // Step 3: Process annotations
  await page.getByRole("button", { name: /Process 2 annotation/ }).click();

  // Step 4: Results view — changeset review
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
  await expect(page.getByText("create", { exact: true })).toBeVisible();
});

test("can toggle annotations before processing", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Attention Is All You Need").click();
  await expect(page.getByText("2 of 2 selected")).toBeVisible();

  // Uncheck first annotation
  const checkboxes = page.locator('input[type="checkbox"]');
  await checkboxes.first().uncheck();
  await expect(page.getByText("1 of 2 selected")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Process 1 annotation/ })
  ).toBeVisible();
});

test("deselect all disables process button", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Attention Is All You Need").click();

  await page.getByText("Deselect All").click();
  await expect(page.getByText("0 of 2 selected")).toBeVisible();

  const processBtn = page.getByRole("button", { name: /Process 0/ });
  await expect(processBtn).toBeDisabled();
});

test("back button returns to papers list", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Attention Is All You Need").click();
  await expect(page.getByText("2 of 2 selected")).toBeVisible();

  // Click back
  await page.getByTitle("Back to papers").click();
  await expect(page.getByText("Zotero Library")).toBeVisible();
});

test("step indicator navigates back to papers", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Attention Is All You Need").click();
  await expect(page.getByText("2 of 2 selected")).toBeVisible();

  // Papers breadcrumb should be clickable
  await page.getByRole("button", { name: "Papers" }).click();
  await expect(page.getByText("Zotero Library")).toBeVisible();
});
