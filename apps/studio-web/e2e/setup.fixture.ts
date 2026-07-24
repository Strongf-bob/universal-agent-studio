import {expect, test as setup} from "@playwright/test";
import {readFileSync} from "node:fs";
import path from "node:path";

import {ownerName, ownerPassword} from "./constants";

const authFile = path.resolve("../../.local/playwright/auth.json");
const fixtureFile = path.resolve(
  "../../contracts/examples/v0.1.0/valid/agent.calculator.ru-en.json",
);
setup("create the local owner and activate the golden AgentSpec", async ({page}) => {
  const status = await page.request.get("/api/v1/bootstrap/status");
  expect(status.ok()).toBeTruthy();
  const bootstrapStatus = (await status.json()) as {bootstrap_required: boolean};

  if (!bootstrapStatus.bootstrap_required) {
    await page.goto("/en-US/login");
    await page.getByLabel("Owner name").fill(ownerName);
    await page.getByLabel("Password").fill(ownerPassword);
    const loginResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/session") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", {name: "Sign in"}).click();
    expect((await loginResponse).status()).toBe(201);
    await expect(page).toHaveURL(/\/en-US\/agents\/import$/);
  } else {
    await page.goto("/en-US/setup");
    await page.getByLabel("Owner name").fill(ownerName);
    await page.getByLabel("Password", {exact: true}).fill(ownerPassword);
    await page.getByLabel("Confirm password").fill(ownerPassword);
    const bootstrapResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/bootstrap/owner") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", {name: "Create owner"}).click();
    expect((await bootstrapResponse).status()).toBe(201);
    await expect(page).toHaveURL(/\/en-US\/agents\/import$/);
  }

  await page.getByLabel("AgentSpec JSON file").setInputFiles(fixtureFile);
  await page.getByRole("button", {name: "Import and validate"}).click();
  await expect(page.getByText("Valid AgentSpec")).toBeVisible();
  await expect(page.getByText("calculator-agent-v1")).toBeVisible();
  await expect(page.locator(".monoValue")).toHaveText(/^[0-9a-f]{64}$/);
  await page.getByRole("button", {name: "Activate version"}).click();
  await expect(page).toHaveURL(/\/en-US\/agents\/calculator-agent$/);

  const agentSpec = JSON.parse(readFileSync(fixtureFile, "utf8")) as {
    nodes: Array<{id: string}>;
  };
  const resetStatus = await page.evaluate(async (specification) => {
    const session = await fetch("/api/v1/session", {
      credentials: "include",
    });
    const {csrf_token: csrfToken} = (await session.json()) as {
      csrf_token: string;
    };
    const created = await fetch(
      "/api/v1/agents/calculator-agent/draft",
      {
        method: "POST",
        credentials: "include",
        headers: {"X-CSRF-Token": csrfToken},
      },
    );
    if (!created.ok) {
      return created.status;
    }
    const current = (await created.json()) as {revision: number};
    const reset = await fetch(
      "/api/v1/agents/calculator-agent/draft",
      {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({
          expected_revision: current.revision,
          agent_spec: specification,
          layout: {
            nodes: specification.nodes.map((node, index) => ({
              node_id: node.id,
              x: index * 260,
              y: index % 2 === 0 ? 80 : 200,
            })),
            viewport: {x: 0, y: 0, zoom: 1},
          },
        }),
      },
    );
    return reset.status;
  }, agentSpec);
  expect(resetStatus).toBe(200);

  await page.context().storageState({path: authFile});
});
