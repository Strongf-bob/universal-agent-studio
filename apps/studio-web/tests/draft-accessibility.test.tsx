import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe, expect, it, vi} from "vitest";

import {BulkDiffPanel} from "@/features/drafts/BulkDiffPanel";
import {DraftGraphTable} from "@/features/drafts/DraftGraphTable";
import {SimpleSettings} from "@/features/drafts/SimpleSettings";

import {editorDraftFixture} from "./draft-fixtures";
import {WithMessages} from "./run-fixtures";

describe("draft editor accessibility", () => {
  it("labels settings and exposes validation beside its field", () => {
    const draft = editorDraftFixture();
    render(
      <WithMessages locale="ru-RU">
        <SimpleSettings
          agentSpec={draft.agent_spec}
          issues={[
            {
              code: "required",
              json_pointer: "/localized_metadata/name/ru-RU",
              node_id: null,
              message_key: "validation.required",
            },
          ]}
          onEdit={vi.fn()}
        />
      </WithMessages>,
    );

    const input = screen.getByRole("textbox", {name: "Название на русском"});
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Обязательное поле",
    );
  });

  it("offers named keyboard alternatives for every graph movement", () => {
    render(
      <WithMessages>
        <DraftGraphTable
          locale="en-US"
          nodes={[
            {
              id: "planner-model",
              label: "Planner",
              description: "Plans",
              kind: "model",
              position: {x: 240, y: 160},
              status: "pending",
              invalid: false,
            },
          ]}
          selectedNodeId={null}
          onMove={vi.fn()}
          onSelect={vi.fn()}
        />
      </WithMessages>,
    );

    for (const direction of ["left", "right", "up", "down"]) {
      expect(
        screen.getByRole("button", {
          name: `Move Planner ${direction}`,
        }),
      ).toBeEnabled();
    }
  });

  it("keeps preview and apply as separate actions", async () => {
    const user = userEvent.setup();
    const draft = editorDraftFixture();
    const onPreview = vi.fn(async () => ({
      draft_id: draft.draft_id,
      revision: draft.revision,
      candidate_digest: "c".repeat(64),
      validation: {valid: true, issues: []},
      operations: [
        {
          op: "replace" as const,
          json_pointer: "/localized_metadata/name/en-US",
          before: "Calculator Agent",
          after: "Math Agent",
        },
      ],
    }));
    const onApply = vi.fn(async () => undefined);
    render(
      <WithMessages>
        <BulkDiffPanel
          agentSpec={draft.agent_spec}
          revision={draft.revision}
          onApply={onApply}
          onPreview={onPreview}
        />
      </WithMessages>,
    );

    await user.click(screen.getByRole("button", {name: "Preview changes"}));
    expect(onPreview).toHaveBeenCalledOnce();
    expect(onApply).not.toHaveBeenCalled();
    expect(screen.getByText("/localized_metadata/name/en-US")).toBeVisible();
    await user.click(screen.getByRole("button", {name: "Apply preview"}));
    expect(onApply).toHaveBeenCalledOnce();
  });
});
