import {expect, test} from "@playwright/test";

import {ownerName, ownerPassword} from "./constants";

test("keyboard navigation reaches primary controls and node details", async ({
  page,
}) => {
  await page.goto("/en-US/agents/calculator-agent");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", {name: "Skip to content"})).toBeFocused();
  await page.getByRole("link", {name: "Skip to content"}).press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.getByLabel("Arithmetic problem").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", {name: "Run"})).toBeFocused();
});

test("logout clears the session and login restores access without storing secrets", async ({
  page,
}) => {
  await page.context().clearCookies();
  await page.goto("/en-US/login");
  await page.getByLabel("Owner name").fill(ownerName);
  await page.getByLabel("Password").fill(ownerPassword);
  await page.getByRole("button", {name: "Sign in"}).click();
  await expect(page).toHaveURL(/\/en-US\/agents\/calculator-agent$/);

  await page.getByRole("button", {name: "Sign out"}).click();
  await expect(page).toHaveURL(/\/en-US\/login$/);

  await page.getByLabel("Owner name").fill(ownerName);
  await page.getByLabel("Password").fill(ownerPassword);
  await page.getByRole("button", {name: "Sign in"}).click();
  await expect(page).toHaveURL(/\/en-US\/agents\/calculator-agent$/);

  const storage = await page.evaluate(() => ({
    local: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
    html: document.documentElement.outerHTML,
  }));
  expect(JSON.stringify(storage)).not.toContain(ownerPassword);
});
