import { expect, test } from "@playwright/test";

test("completes a real OIDC, FastAPI, PostgreSQL and DeepSeek query", async ({
  page,
}) => {
  test.skip(
    process.env.PLAYWRIGHT_LIVE !== "1",
    "Set PLAYWRIGHT_LIVE=1 with Keycloak, FastAPI and PostgreSQL running",
  );
  test.setTimeout(180_000);

  await page.goto("/");
  await page.waitForURL(/\/realms\/ida\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill("developer");
  await page.locator("#password").fill("ida-dev-password");
  await page.locator("#kc-login").click();

  await expect(
    page.getByRole("heading", { name: "数据分析工作区" }),
  ).toBeVisible({ timeout: 30_000 });
  await page
    .getByPlaceholder("用自然语言描述你想了解的数据...")
    .fill("查询今年各区域月销售额并生成趋势图");
  await page.getByRole("button", { name: "开始分析" }).click();

  await expect(page.getByText("执行链路已完成", { exact: false })).toBeVisible({
    timeout: 150_000,
  });
  await page.getByRole("tab", { name: "SQL" }).click();
  await expect(
    page.getByText("SELECT", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("tab", { name: "数据表" }).click();
  await expect(page.getByText("结果数据")).toBeVisible();
});
