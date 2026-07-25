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

async function ensureV1Traffic(page: Page): Promise<void> {
  const response = await page.request.get(
    `${studioBase}/api/v1/agents/calculator-agent/publishing`,
  );
  expect(response.ok()).toBeTruthy();
  const state = (await response.json()) as {
    active_version_id: string;
  };
  if (state.active_version_id === "calculator-agent-v1") {
    return;
  }
  const session = await page.request.get(`${studioBase}/api/v1/session`);
  const {csrf_token: csrfToken} = (await session.json()) as {
    csrf_token: string;
  };
  const rollback = await page.request.post(
    `${studioBase}/api/v1/agents/calculator-agent/rollback`,
    {
      headers: {"X-CSRF-Token": csrfToken},
      data: {
        target_version_id: "calculator-agent-v1",
        expected_active_version_id: state.active_version_id,
      },
    },
  );
  expect(rollback.status()).toBe(200);
}

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
  await ensureV1Traffic(page);
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

  const publicationState = await page.request.get(
    `${studioBase}/api/v1/agents/calculator-agent/publishing`,
  );
  expect(publicationState.ok()).toBeTruthy();
  const state = (await publicationState.json()) as {
    draft_digest: string;
    active_version_id: string;
    events: Array<{event_id: string}>;
    versions: Array<{version_id: string; digest: string}>;
  };
  const previousEventCount = state.events.length;
  const pristineVersionHistory = state.versions.length <= 2;
  const activeDigest = state.versions.find(
    (version) => version.version_id === state.active_version_id,
  )?.digest;
  expect(activeDigest).toBeTruthy();
  if (state.draft_digest === activeDigest) {
    await page.goto(`${studioBase}/en-US/agents/calculator-agent/build`);
    await page
      .getByRole("textbox", {name: "Name in English"})
      .fill("Published Calculator v2");
    await page.getByRole("button", {name: "Save draft"}).click();
    await expect(page.getByText("Draft saved")).toBeVisible();
  }
  await page.goto(`${studioBase}/en-US/agents/calculator-agent/publish`);

  await page.getByRole("button", {name: /Publish revision/}).click();
  const publishedState = await page.request.get(
    `${studioBase}/api/v1/agents/calculator-agent/publishing`,
  );
  expect(publishedState.ok()).toBeTruthy();
  const publishedVersionId = (
    (await publishedState.json()) as {active_version_id: string}
  ).active_version_id;
  expect(publishedVersionId).not.toBe("calculator-agent-v1");
  if (pristineVersionHistory) {
    expect(publishedVersionId).toBe("calculator-agent-v2");
  }
  await expect(page.getByText(`Traffic: ${publishedVersionId}`)).toBeVisible();

  const changedVersionRun = await runPublishedAgent(page);
  expect(changedVersionRun.agent_version_id).toBe(publishedVersionId);

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
  ).toBe(previousEventCount + 2);

  const boundRun = await page.request.get(
    `${publishedBase}${changedVersionRun.status_url}`,
    {
      headers: {Authorization: `Bearer ${changedVersionRun.run_capability}`},
    },
  );
  expect(boundRun.ok()).toBeTruthy();
  expect((await boundRun.json()).agent_version_id).toBe(publishedVersionId);

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
