import {expect, type Locator, type Page} from "@playwright/test";

export async function startRun(page: Page): Promise<string> {
  await page.goto("/en-US/agents/calculator-agent");
  await expect(page.getByRole("heading", {name: "Calculator agent"})).toBeVisible();
  await expect(page.getByText("Immutable version")).toBeVisible();
  await page.getByLabel("Arithmetic problem").fill("What is 19 × 23?");
  await page.getByRole("button", {name: "Run"}).click();
  await expect(page).toHaveURL(/\/en-US\/runs\/[0-9a-f-]+$/);
  return page.url().split("/").at(-1) ?? "";
}

export async function openDraft(page: Page): Promise<number> {
  await page.goto("/en-US/agents/calculator-agent/build");
  await expect(page.locator(".draftIdentity h1")).toBeVisible();
  return draftRevision(page);
}

export async function draftRevision(page: Page): Promise<number> {
  const text = await page.locator(".revisionBadge").innerText();
  const match = text.match(/\d+/);
  expect(match).not.toBeNull();
  return Number(match?.[0]);
}

export function draftNodeRow(page: Page, label: string): Locator {
  return page
    .getByRole("table", {name: "Editable agent graph nodes"})
    .getByRole("row")
    .filter({has: page.getByRole("button", {name: `Select ${label}`})});
}
