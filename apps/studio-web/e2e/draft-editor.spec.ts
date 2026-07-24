import {expect, test} from "@playwright/test";

import {
  draftNodeRow,
  draftRevision,
  openDraft,
} from "./helpers";

test("one canonical draft survives both editors, validation, run and locale", async ({
  page,
}) => {
  const firstRevision = await openDraft(page);
  const nameField = page.getByRole("textbox", {
    name: "Name in English",
    exact: true,
  });
  await nameField.fill("Calculator Studio Agent");

  const plannerRow = draftNodeRow(page, "Planner");
  await plannerRow.getByRole("button", {name: "Select Planner"}).click();
  const prompt = page.getByLabel("Prompt in English");
  await prompt.fill("Return a typed operation and exactly two numbers.");
  const initialPosition = await plannerRow.locator(".positionCell").innerText();
  await plannerRow.getByRole("button", {name: "Move Planner right"}).click();
  await page.getByRole("button", {name: "Save draft"}).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved");
  expect(await draftRevision(page)).toBe(firstRevision + 1);

  await page.reload();
  await expect(nameField).toHaveValue("Calculator Studio Agent");
  await draftNodeRow(page, "Planner")
    .getByRole("button", {name: "Select Planner"})
    .click();
  await expect(prompt).toHaveValue(
    "Return a typed operation and exactly two numbers.",
  );
  await expect(
    draftNodeRow(page, "Planner").locator(".positionCell"),
  ).not.toHaveText(initialPosition);

  const modelProfile = page.getByLabel("Model profile");
  await modelProfile.fill("missing-model-profile");
  await page.getByRole("button", {name: "Save draft"}).click();
  await expect(page.getByRole("status")).toContainText("not saved");
  await expect(modelProfile).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#node-model-profile-error")).toHaveText(
    "Invalid value",
  );

  await modelProfile.fill("deterministic-planner");
  await page.getByRole("button", {name: "Save draft"}).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved");

  const beforeBulkName = await nameField.inputValue();
  const bulk = page.getByRole("textbox", {
    name: "Complete AgentSpec JSON",
    exact: true,
  });
  const candidate = JSON.parse(await bulk.inputValue()) as {
    localized_metadata: {
      name: Record<string, string>;
      description: Record<string, string>;
    };
  };
  candidate.localized_metadata.name["en-US"] = "Agent Lab";
  candidate.localized_metadata.description["en-US"] =
    "A draft edited through the safe JSON preview.";
  await bulk.fill(JSON.stringify(candidate, null, 2));
  await page.getByRole("button", {name: "Preview changes"}).click();
  await expect(
    page.getByRole("table", {name: "AgentSpec change preview"}),
  ).toBeVisible();
  await expect(page.getByText("2 change(s) in this preview")).toBeVisible();
  await expect(nameField).toHaveValue(beforeBulkName);
  await page.getByRole("button", {name: "Apply preview"}).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved");
  await expect(nameField).toHaveValue("Agent Lab");

  await page.getByLabel("Arithmetic problem").fill("What is 19 × 23?");
  await page.getByRole("button", {name: "Run saved draft"}).click();
  const runHistory = page.getByRole("log", {
    name: "Draft run node history",
  });
  await expect(
    runHistory.getByRole("listitem", {name: "Planner · Running"}),
  ).toBeVisible();
  await expect(
    runHistory.getByRole("listitem", {name: "Planner · Completed"}),
  ).toBeVisible();
  await expect(
    draftNodeRow(page, "Planner").getByText("Completed", {exact: true}),
  ).toBeVisible();
  await expect(page.getByText('{"value":437}', {exact: true})).toBeVisible();
  await expect(page.locator(".draftCanvas [tabindex='0']")).toHaveCount(0);

  const draftBeforeLocale = await page.request.get(
    "/api/v1/agents/calculator-agent/draft",
  );
  const revisionBeforeLocale = (
    (await draftBeforeLocale.json()) as {revision: number}
  ).revision;
  const runId = await page.locator(".testRunMeta code").innerText();
  await page.getByRole("link", {name: "Language"}).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/ru-RU/agents/calculator-agent/build\\?.*node=planner-model.*run=${runId}`,
    ),
  );
  await expect(
    page.getByRole("heading", {name: "Настройки «Планировщик»"}),
  ).toBeVisible();
  await expect(page.getByText(runId, {exact: true})).toBeVisible();
  await page.getByRole("link", {name: "Язык"}).click();
  await expect(page).toHaveURL(
    new RegExp(`/en-US/agents/calculator-agent/build\\?.*run=${runId}`),
  );
  await page.getByRole("link", {name: "Open full trace"}).click();
  await expect(page).toHaveURL(/\/en-US\/runs\/[0-9a-f-]+$/);
  await expect(page.getByText(runId, {exact: true})).toBeVisible();
  const draftAfterLocale = await page.request.get(
    "/api/v1/agents/calculator-agent/draft",
  );
  expect(
    ((await draftAfterLocale.json()) as {revision: number}).revision,
  ).toBe(revisionBeforeLocale);
});

test("narrow layout keeps graph selection and movement keyboard-operable", async ({
  page,
}) => {
  await page.setViewportSize({width: 390, height: 844});
  await openDraft(page);
  await page.getByRole("tab", {name: "Simple"}).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", {name: "Graph"})).toBeFocused();
  await expect(
    page.getByRole("region", {name: "Agent basics"}),
  ).toBeHidden();
  await expect(
    page.getByRole("table", {name: "Editable agent graph nodes"}),
  ).toBeVisible();
  const plannerRow = draftNodeRow(page, "Planner");
  const select = plannerRow.getByRole("button", {name: "Select Planner"});
  await select.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", {name: "Planner settings"}),
  ).toBeVisible();

  await page.getByRole("tab", {name: "Graph"}).click();
  const before = await plannerRow.locator(".positionCell").innerText();
  const moveDown = plannerRow.getByRole("button", {
    name: "Move Planner down",
  });
  await moveDown.focus();
  await page.keyboard.press("Enter");
  await expect(plannerRow.locator(".positionCell")).not.toHaveText(before);
  await expect(page.locator(".draftCanvas")).toBeHidden();

  await page.getByRole("tab", {name: "Inspector"}).click();
  const storageProbe = "slice2-browser-storage-probe-47a1c3";
  await page.getByLabel("Prompt in English").fill(storageProbe);
  const storage = await page.evaluate(() => ({
    local: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
  }));
  expect(JSON.stringify(storage)).not.toContain(storageProbe);
});
