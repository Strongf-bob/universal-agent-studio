import {expect, test} from "@playwright/test";

test("published event stream resumes from the last observed sequence", async ({
  page,
}) => {
  const observedLastEventIds: string[] = [];
  let firstStream = true;
  await page.route("**/public/v1/agents/*/runs/*/events", async (route) => {
    observedLastEventIds.push(
      route.request().headers()["last-event-id"] ?? "",
    );
    if (firstStream) {
      firstStream = false;
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: [
          "id: 2",
          "event: run.progress",
          `data: ${JSON.stringify({
            schema_version: "0.1.0",
            sequence: 2,
            type: "run.progress",
            status: "running",
            occurred_at: "2026-07-25T12:00:00Z",
            output: null,
            error_code: null,
          })}`,
          "",
          "",
        ].join("\n"),
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/en-US/agents/calculator-agent");
  await page.getByLabel("Arithmetic problem").fill("What is 19 × 23?");
  await page.getByRole("button", {name: "Run agent"}).click();

  await expect(page.getByRole("status")).toContainText("437");
  expect(observedLastEventIds[0]).toBe("0");
  expect(observedLastEventIds).toContain("2");
});
