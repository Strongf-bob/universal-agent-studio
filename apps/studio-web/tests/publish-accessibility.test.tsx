import {render, screen} from "@testing-library/react";
import {expect, it, vi} from "vitest";

import {PublishWorkspace} from "@/features/publishing/PublishWorkspace";

import {WithMessages} from "./run-fixtures";

it("provides labelled publishing regions and keyboard controls", () => {
  render(
    <WithMessages>
      <PublishWorkspace
        agentId="calculator-agent"
        locale="en-US"
        initialState={{
          schema_version: "0.1.0",
          agent_id: "calculator-agent",
          draft_revision: 2,
          draft_digest: "a".repeat(64),
          active_version_id: "calculator-v1",
          versions: [
            {
              version_id: "calculator-v1",
              version_number: 1,
              digest: "b".repeat(64),
              created_at: "2026-07-25T10:00:00Z",
            },
          ],
          events: [],
          api_keys: [],
          webhooks: [],
        }}
        api={{
          refresh: vi.fn(),
          publish: vi.fn(),
          rollback: vi.fn(),
          createApiKey: vi.fn(),
          revokeApiKey: vi.fn(),
          createWebhook: vi.fn(),
          revokeWebhook: vi.fn(),
        }}
      />
    </WithMessages>,
  );

  expect(screen.getByRole("heading", {name: "Publish agent"})).toBeVisible();
  expect(screen.getByRole("region", {name: "Version history"})).toBeVisible();
  expect(screen.getByRole("region", {name: "API keys"})).toBeVisible();
  expect(screen.getByRole("region", {name: "Webhooks"})).toBeVisible();
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
});
