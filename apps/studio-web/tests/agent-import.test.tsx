import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {NextIntlClientProvider} from "next-intl";
import {describe, expect, it, vi} from "vitest";

import {AgentImportForm} from "@/features/agents/AgentImportForm";
import enMessages from "@/messages/en-US.json";

describe("AgentImportForm", () => {
  it("imports, shows validation evidence, and activates through visible controls", async () => {
    const user = userEvent.setup();
    const importVersion = vi.fn().mockResolvedValue({
      version_id: "calculator-agent-v1",
      agent_id: "calculator-agent",
      schema_version: "0.1.0",
      digest: "a".repeat(64),
      validation: {valid: true, issues: []},
      reused: false,
    });
    const activateVersion = vi.fn().mockResolvedValue(undefined);
    const onActivated = vi.fn();
    render(
      <NextIntlClientProvider locale="en-US" messages={enMessages}>
        <AgentImportForm
          locale="en-US"
          importVersion={importVersion}
          activateVersion={activateVersion}
          onActivated={onActivated}
        />
      </NextIntlClientProvider>,
    );
    const fixture = new File(["{}"], "agent.json", {
      type: "application/json",
    });

    await user.upload(screen.getByLabelText("AgentSpec JSON file"), fixture);
    await user.click(screen.getByRole("button", {name: "Import and validate"}));

    expect(importVersion).toHaveBeenCalledWith(fixture);
    expect(await screen.findByText("Valid AgentSpec")).toBeVisible();
    expect(screen.getByText("calculator-agent-v1")).toBeVisible();
    expect(screen.getByText("a".repeat(64))).toBeVisible();

    await user.click(screen.getByRole("button", {name: "Activate version"}));
    expect(activateVersion).toHaveBeenCalledWith(
      "calculator-agent",
      "calculator-agent-v1",
    );
    expect(onActivated).toHaveBeenCalledWith("calculator-agent");
  });
});
