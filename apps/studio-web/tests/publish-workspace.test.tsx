import type {
  ApiKeyCreateView,
  PublicationState,
  WebhookCreateView,
} from "@universal-agent-studio/contracts";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe, expect, it, vi} from "vitest";

import {PublishWorkspace} from "@/features/publishing/PublishWorkspace";
import type {PublishingApi} from "@/features/publishing/types";
import {ApiClientError} from "@/lib/api/client";

import {WithMessages} from "./run-fixtures";

function state(
  activeVersionId = "calculator-v1",
  withV2 = false,
): PublicationState {
  const versions = [
    {
      version_id: "calculator-v1",
      version_number: 1,
      digest: "a".repeat(64),
      created_at: "2026-07-25T10:00:00Z",
    },
  ];
  if (withV2) {
    versions.push({
      version_id: "calculator-v2",
      version_number: 2,
      digest: "b".repeat(64),
      created_at: "2026-07-25T11:00:00Z",
    });
  }
  return {
    schema_version: "0.1.0",
    agent_id: "calculator-agent",
    draft_revision: 2,
    draft_digest: "c".repeat(64),
    active_version_id: activeVersionId,
    versions,
    events: withV2
      ? [
          {
            event_id: "11111111-1111-4111-8111-111111111111",
            event_type: "publish",
            previous_version_id: null,
            selected_version_id: "calculator-v1",
            selected_version_digest: "a".repeat(64),
            created_at: "2026-07-25T10:00:00Z",
          },
          {
            event_id: "22222222-2222-4222-8222-222222222222",
            event_type: "publish",
            previous_version_id: "calculator-v1",
            selected_version_id: "calculator-v2",
            selected_version_digest: "b".repeat(64),
            created_at: "2026-07-25T11:00:00Z",
          },
        ]
      : [],
    api_keys: [],
    webhooks: [],
  };
}

function apiFixture(): PublishingApi {
  const v2 = state("calculator-v2", true);
  const rolledBack: PublicationState = {
    ...v2,
    active_version_id: "calculator-v1",
    events: [
      ...v2.events,
      {
        event_id: "33333333-3333-4333-8333-333333333333",
        event_type: "rollback",
        previous_version_id: "calculator-v2",
        selected_version_id: "calculator-v1",
        selected_version_digest: "a".repeat(64),
        created_at: "2026-07-25T12:00:00Z",
      },
    ],
  };
  return {
    refresh: vi.fn(async () => v2),
    publish: vi.fn(async () => v2),
    rollback: vi.fn(async () => rolledBack),
    createApiKey: vi.fn(),
    revokeApiKey: vi.fn(),
    createWebhook: vi.fn(),
    revokeWebhook: vi.fn(),
  };
}

describe("Publish workspace", () => {
  it("publishes v2 then switches traffic back to immutable v1", async () => {
    const user = userEvent.setup();
    const api = apiFixture();
    render(
      <WithMessages>
        <PublishWorkspace
          agentId="calculator-agent"
          initialState={state()}
          locale="en-US"
          api={api}
        />
      </WithMessages>,
    );

    await user.click(
      screen.getByRole("button", {name: "Publish revision 2"}),
    );
    expect(await screen.findByText("Traffic: calculator-v2")).toBeVisible();
    await user.click(
      screen.getByRole("button", {
        name: "Switch traffic to calculator-v1",
      }),
    );
    expect(await screen.findByText("Traffic: calculator-v1")).toBeVisible();
    expect(
      screen.getAllByRole("row", {name: /publish|rollback/i}),
    ).toHaveLength(3);
  });

  it("shows an issued API key once and removes it on dismiss", async () => {
    const user = userEvent.setup();
    const secret = `uas_live_0123456789abcdef_${"A".repeat(43)}`;
    const created: ApiKeyCreateView = {
      key_id: "11111111-1111-4111-8111-111111111111",
      label: "Local client",
      prefix: "0123456789abcdef",
      scopes: ["runs:create", "runs:read", "events:read"],
      expires_at: null,
      created_at: "2026-07-25T10:00:00Z",
      last_used_at: null,
      revoked_at: null,
      secret,
    };
    const api = apiFixture();
    api.createApiKey = vi.fn(async () => created);
    render(
      <WithMessages>
        <PublishWorkspace
          agentId="calculator-agent"
          initialState={state()}
          locale="en-US"
          api={api}
        />
      </WithMessages>,
    );

    await user.type(screen.getByRole("textbox", {name: "Key label"}), "Local client");
    await user.click(screen.getByRole("button", {name: "Create API key"}));
    const secretPanel = await screen.findByRole("alert");
    expect(secretPanel).toHaveTextContent(secret);
    await user.click(within(secretPanel).getByRole("button", {name: "Dismiss"}));
    expect(screen.queryByText(secret)).not.toBeInTheDocument();
  });

  it("refreshes authoritative state after a publication conflict", async () => {
    const user = userEvent.setup();
    const api = apiFixture();
    api.publish = vi.fn(async () => {
      throw new ApiClientError("draft_revision_conflict", null, false);
    });
    render(
      <WithMessages>
        <PublishWorkspace
          agentId="calculator-agent"
          initialState={state()}
          locale="en-US"
          api={api}
        />
      </WithMessages>,
    );
    await user.click(
      screen.getByRole("button", {name: "Publish revision 2"}),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Publishing state changed",
    );
    expect(api.refresh).toHaveBeenCalledOnce();
  });

  it("creates a terminal webhook and never persists issued secrets", async () => {
    const user = userEvent.setup();
    const api = apiFixture();
    api.createWebhook = vi.fn(async () => webhookCreateFixture);
    render(
      <WithMessages>
        <PublishWorkspace
          agentId="calculator-agent"
          initialState={state()}
          locale="en-US"
          api={api}
        />
      </WithMessages>,
    );

    await user.type(screen.getByRole("textbox", {name: "Webhook label"}), "Terminal");
    await user.type(
      screen.getByRole("textbox", {name: "Target URL"}),
      "https://hooks.example.test/terminal",
    );
    await user.click(screen.getByRole("button", {name: "Create webhook"}));

    expect(await screen.findByText(webhookCreateFixture.secret)).toBeVisible();
    expect(api.createWebhook).toHaveBeenCalledWith({
      agentId: "calculator-agent",
      request: {
        label: "Terminal",
        target_url: "https://hooks.example.test/terminal",
        events: ["run.completed", "run.failed", "run.cancelled"],
      },
    });
    const source = [
      "PublishWorkspace.tsx",
      "CredentialPanel.tsx",
      "WebhookPanel.tsx",
    ]
      .map((file) =>
        readFileSync(
          resolve(process.cwd(), `src/features/publishing/${file}`),
          "utf8",
        ),
      )
      .join("\n");
    expect(source).not.toMatch(
      /localStorage|sessionStorage|document\.cookie|console\.(log|info|warn|error)/,
    );
  });
});

export const webhookCreateFixture: WebhookCreateView = {
  subscription_id: "44444444-4444-4444-8444-444444444444",
  label: "Terminal",
  target_url: "https://hooks.example.test/terminal",
  events: ["run.completed"],
  created_at: "2026-07-25T10:00:00Z",
  revoked_at: null,
  secret: `uas_whsec_${"B".repeat(43)}`,
};
