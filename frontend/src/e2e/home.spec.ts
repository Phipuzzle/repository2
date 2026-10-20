import { expect, test } from "@playwright/test";

test("home page renders the workspace", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Intelligent Data Agent")).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据分析工作区" })).toBeVisible();
  await expect(page.getByRole("textbox")).toBeVisible();
  await expect(page.getByRole("tab", { name: "图表" })).toBeVisible();
});
