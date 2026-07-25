import {expect, test, type Page} from "@playwright/test";

const studioBase = process.env.UAS_E2E_BASE_URL ?? "http://localhost:3000";
const publishedBase =
  process.env.UAS_E2E_PUBLISHED_BASE_URL ?? "http://127.0.0.1:3301";

type CreatedPublicRun = {
  run_id: string;
  agent_version_id: string;
  run_capability: string;
  status_url: string;
};

async function runPublishedAgent(page: Page): Promise<CreatedPublicRun> {
  const response = page.waitForResponse(
    (candidate) =>
      candidate.url().includes("/public/v1/agents/calculator-agent/runs") &&
      candidate.request().method() === "POST",
  );
  await page.goto(`${publishedBase}/en-US/agents/calculator-agent`);
  await page.getByLabel("Arithmetic problem").fill("What is 19 × 23?");
  await page.getByRole("button", {name: "Run agent"}).click();
  const created = (await (await response).json()) as CreatedPublicRun;
  await expect(page.getByRole("status")).toContainText("437");
  return created;
}

test("publishes v2, binds its run, and switches traffic to immutable v1", async ({
  page,
}) => {
  const v1Run = await runPublishedAgent(page);
  expect(v1Run.agent_version_id).toBe("calculator-agent-v1");

  await page.goto(
    `${studioBase}/en-US/agents/calculator-agent/publish`,
  );
  await expect(page.getByText("Traffic: calculator-agent-v1")).toBeVisible();

  await page.getByRole("textbox", {name: "Key label"}).fill("E2E client");
  await page.getByRole("button", {name: "Create API key"}).click();
  const keyAlert = page.getByRole("alert");
  const issuedKey = await keyAlert.locator("code").innerText();
  expect(issuedKey).toMatch(/^uas_live_/);
  await keyAlert.getByRole("button", {name: "Dismiss"}).click();
  await page
    .getByRole("listitem")
    .filter({hasText: "E2E client"})
    .getByRole("button", {name: "Revoke"})
    .click();

  await page.goto(`${studioBase}/en-US/agents/calculator-agent/build`);
  await page
    .getByRole("textbox", {name: "Name in English"})
    .fill("Published Calculator v2");
  await page.getByRole("button", {name: "Save draft"}).click();
  await expect(page.getByText("Draft saved")).toBeVisible();
  await page.goto(`${studioBase}/en-US/agents/calculator-agent/publish`);

  await page.getByRole("button", {name: /Publish revision/}).click();
  await expect(page.getByText("Traffic: calculator-agent-v2")).toBeVisible();

  const v2Run = await runPublishedAgent(page);
  expect(v2Run.agent_version_id).toBe("calculator-agent-v2");

  await page.goto(
    `${studioBase}/en-US/agents/calculator-agent/publish`,
  );
  await page
    .getByRole("button", {
      name: "Switch traffic to calculator-agent-v1",
    })
    .click();
  await expect(page.getByText("Traffic: calculator-agent-v1")).toBeVisible();
  expect(
    await page.getByRole("row", {name: /publish|rollback/i}).count(),
  ).toBe(3);

  const boundRun = await page.request.get(
    `${publishedBase}${v2Run.status_url}`,
    {
      headers: {Authorization: `Bearer ${v2Run.run_capability}`},
    },
  );
  expect(boundRun.ok()).toBeTruthy();
  expect((await boundRun.json()).agent_version_id).toBe(
    "calculator-agent-v2",
  );

  await page.getByRole("textbox", {name: "Webhook label"}).fill("E2E terminal");
  await page
    .getByRole("textbox", {name: "Target URL"})
    .fill("https://hooks.example.test/terminal");
  await page.getByRole("button", {name: "Create webhook"}).click();
  const webhookAlert = page.getByRole("alert");
  await expect(webhookAlert.locator("code")).toContainText("whsec_");
  await webhookAlert.getByRole("button", {name: "Dismiss"}).click();
  await page
    .getByRole("listitem")
    .filter({hasText: "E2E terminal"})
    .getByRole("button", {name: "Revoke"})
    .click();

  const browserState = await page.evaluate(() => ({
    local: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
    html: document.documentElement.outerHTML,
  }));
  expect(JSON.stringify(browserState)).not.toContain(issuedKey);
  expect(browserState.html).toContain("YOUR_API_KEY");
});
