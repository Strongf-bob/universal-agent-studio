import {expect, test} from "@playwright/test";

import {startRun} from "./helpers";

test("refresh resumes events without duplicate terminal result", async ({page}) => {
  const runId = await startRun(page);
  await page.reload();
  await expect(page.getByText("Run completed")).toBeVisible();
  await expect(
    page
      .getByRole("region", {name: "Execution completed"})
      .getByText('{"value":437}', {exact: true}),
  ).toBeVisible();
  await expect(page.getByText(runId, {exact: true})).toBeVisible();
  await expect(page.getByText("Run completed")).toHaveCount(1);
});

test("a delayed run can be cancelled and leaves a readable trace", async ({
  page,
}) => {
  await page.goto("/en-US/agents/calculator-agent");
  await page.getByRole("button", {name: "Run"}).click();
  await expect(page).toHaveURL(/\/en-US\/runs\/[0-9a-f-]+$/);
  await page.getByRole("button", {name: "Cancel run"}).click();
  await expect(page.getByText("Run cancelled")).toBeVisible();
  await expect(page.getByText("Execution cancelled")).toBeVisible();
});
