import {expect, test as setup} from "@playwright/test";
import {readFile} from "node:fs/promises";
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
  }

  const session = await page.request.get("/api/v1/session");
  expect(session.ok()).toBeTruthy();
  const csrf = ((await session.json()) as {csrf_token: string}).csrf_token;
  const fixture = JSON.parse(await readFile(fixtureFile, "utf8")) as object;
  const imported = await page.request.post("/api/v1/agent-versions/import", {
    data: fixture,
    headers: {
      Origin: "http://localhost:3000",
      "X-CSRF-Token": csrf,
    },
  });
  expect([200, 201]).toContain(imported.status());
  const version = (await imported.json()) as {
    version_id: string;
    digest: string;
    validation: {valid: boolean};
  };
  expect(version.validation.valid).toBe(true);
  expect(version.digest).toMatch(/^[0-9a-f]{64}$/);

  const active = await page.request.get(
    "/api/v1/agents/calculator-agent/active-version",
  );
  if (active.status() === 404) {
    const activated = await page.request.post(
      "/api/v1/agents/calculator-agent/active-version",
      {
        data: {
          version_id: version.version_id,
          expected_previous_version_id: null,
        },
        headers: {
          Origin: "http://localhost:3000",
          "X-CSRF-Token": csrf,
        },
      },
    );
    expect(activated.ok()).toBeTruthy();
  } else {
    expect(active.ok()).toBeTruthy();
  }

  await page.context().storageState({path: authFile});
});
