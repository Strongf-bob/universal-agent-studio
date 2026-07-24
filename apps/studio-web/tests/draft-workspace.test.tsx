import {render, screen, waitFor, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe, expect, it, vi} from "vitest";

import {DraftWorkspace} from "@/features/drafts/DraftWorkspace";

import {editorDraftFixture, savedDraft} from "./draft-fixtures";
import {WithMessages} from "./run-fixtures";

vi.mock("@xyflow/react", () => ({
  Background: () => null,
  Controls: () => null,
  ReactFlow: ({children}: {children: React.ReactNode}) => (
    <div data-testid="draft-canvas">{children}</div>
  ),
}));

describe("dual-view draft workspace", () => {
  it("edits one shared AgentSpec and saves the authoritative revision", async () => {
    const user = userEvent.setup();
    const draft = editorDraftFixture();
    const persistDraft = vi.fn(async (input) =>
      savedDraft(draft, input.agentSpec),
    );
    render(
      <WithMessages>
        <DraftWorkspace
          agentId={draft.agent_id}
          initialDraft={draft}
          locale="en-US"
          persistDraft={persistDraft}
        />
      </WithMessages>,
    );

    const name = screen.getByRole("textbox", {name: "Name in English"});
    await user.clear(name);
    await user.type(name, "Math Agent");

    expect(screen.getByRole("status")).toHaveTextContent("Unsaved changes");
    await user.click(screen.getByRole("button", {name: "Save draft"}));

    expect(persistDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: "calculator-agent",
        expectedRevision: 1,
        agentSpec: expect.objectContaining({
          localized_metadata: expect.objectContaining({
            name: expect.objectContaining({"en-US": "Math Agent"}),
          }),
        }),
      }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Draft saved");
  });

  it("selects and moves the same planner node through the keyboard table", async () => {
    const user = userEvent.setup();
    const draft = editorDraftFixture();
    render(
      <WithMessages>
        <DraftWorkspace
          agentId={draft.agent_id}
          initialDraft={draft}
          locale="en-US"
        />
      </WithMessages>,
    );

    const plannerRow = screen
      .getByRole("button", {name: "Select Planner"})
      .closest("tr");
    expect(plannerRow).not.toBeNull();
    await user.click(
      within(plannerRow as HTMLTableRowElement).getByRole("button", {
        name: "Select Planner",
      }),
    );
    expect(
      screen.getByRole("heading", {name: "Planner settings"}),
    ).toBeVisible();
    expect(
      screen.getByRole("textbox", {name: "Prompt in English"}),
    ).toHaveValue("Return only an operation and two numbers.");

    const before = within(plannerRow as HTMLTableRowElement).getByText(
      "240, 160",
    );
    expect(before).toBeVisible();
    await user.click(
      within(plannerRow as HTMLTableRowElement).getByRole("button", {
        name: "Move Planner right",
      }),
    );
    expect(
      within(plannerRow as HTMLTableRowElement).getByText("264, 160"),
    ).toBeVisible();
  });

  it("does not run an unsaved AgentSpec as a saved revision", async () => {
    const user = userEvent.setup();
    const draft = editorDraftFixture();
    render(
      <WithMessages>
        <DraftWorkspace
          agentId={draft.agent_id}
          initialDraft={draft}
          locale="en-US"
        />
      </WithMessages>,
    );

    const run = screen.getByRole("button", {name: "Run saved draft"});
    expect(run).toBeEnabled();
    await user.type(
      screen.getByRole("textbox", {name: "Name in English"}),
      " changed",
    );

    expect(run).toBeDisabled();
    expect(
      screen.getByText("Save current changes before running."),
    ).toBeVisible();
  });

  it("locks editor controls while a snapshot run is being created", async () => {
    const user = userEvent.setup();
    const draft = editorDraftFixture();
    const startTestRun = vi.fn(
      async () =>
        await new Promise<never>(() => {
          // Intentionally unresolved so the starting state can be observed.
        }),
    );
    const {container} = render(
      <WithMessages>
        <DraftWorkspace
          agentId={draft.agent_id}
          initialDraft={draft}
          locale="en-US"
          startTestRun={startTestRun}
        />
      </WithMessages>,
    );

    await user.type(
      screen.getByRole("textbox", {name: "Arithmetic problem"}),
      "What is 19 × 23?",
    );
    await user.click(
      screen.getByRole("button", {name: "Run saved draft"}),
    );

    await waitFor(() =>
      expect(container.querySelector(".draftWorkbench")).toHaveAttribute(
        "inert",
      ),
    );
    expect(screen.getByRole("button", {name: "Save draft"})).toBeDisabled();
  });
});
