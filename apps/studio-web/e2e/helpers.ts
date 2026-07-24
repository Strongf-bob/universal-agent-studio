import {expect, type Page} from "@playwright/test";

export async function startRun(page: Page): Promise<string> {
  await page.goto("/en-US/agents/calculator-agent");
  await expect(page.getByRole("heading", {name: "Calculator agent"})).toBeVisible();
  await expect(page.getByText("Immutable version")).toBeVisible();
  await page.getByLabel("Arithmetic problem").fill("What is 19 × 23?");
  await page.getByRole("button", {name: "Run"}).click();
  await expect(page).toHaveURL(/\/en-US\/runs\/[0-9a-f-]+$/);
  return page.url().split("/").at(-1) ?? "";
}
