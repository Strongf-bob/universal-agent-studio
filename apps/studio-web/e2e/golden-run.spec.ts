import {expect, test} from "@playwright/test";

import {startRun} from "./helpers";

test("golden run survives refresh and exposes result, graph and trace", async ({
  page,
}) => {
  const runId = await startRun(page);
  await expect(page.getByText("Run completed")).toBeVisible();
  await expect(
    page
      .getByRole("region", {name: "Execution completed"})
      .getByText('{"value":437}', {exact: true}),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByText(runId, {exact: true})).toBeVisible();
  await expect(page.getByText("Execution completed")).toBeVisible();
  await expect(
    page.getByRole("table", {name: "Agent execution nodes"}),
  ).toBeVisible();

  await page.getByRole("button", {name: "Inspect Calculator"}).click();
  await expect(page.getByRole("heading", {name: "Calculator"})).toBeVisible();
  await expect(
    page.getByRole("heading", {name: "Execution", exact: true}),
  ).toBeVisible();
  await expect(page.getByText("attempt", {exact: true})).toBeVisible();
  await expect(page.getByText("builtin-calculator")).toBeVisible();
  await expect(page.getByText("Only values processed by the redaction policy")).toBeVisible();
});

test("locale switch keeps the run identity and changes labels", async ({page}) => {
  const runId = await startRun(page);
  await expect(page.getByText("Run completed")).toBeVisible();
  await page.getByRole("link", {name: "Language"}).click();
  await expect(page).toHaveURL(new RegExp(`/ru-RU/runs/${runId}$`));
  await expect(
    page.getByRole("heading", {name: "Выполнение агента"}),
  ).toBeVisible();
  await expect(page.getByText(runId, {exact: true})).toBeVisible();
});
