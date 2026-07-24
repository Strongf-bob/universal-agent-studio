import {existsSync, readFileSync} from "node:fs";
import {resolve} from "node:path";

import type {AgentDraft} from "@universal-agent-studio/contracts";
import {expect, test} from "vitest";

import {
  draftEditorReducer,
  initialDraftState,
  issuesByNode,
  issuesByPointer,
  replaceAtPointer,
} from "@/features/drafts/editor-state";

function draftFixture(): AgentDraft {
  return JSON.parse(
    readFileSync(
      resolve(
        process.cwd(),
        "../../contracts/examples/v0.1.0/valid/agent.draft.calculator.json",
      ),
      "utf8",
    ),
  ) as AgentDraft;
}

test("canonical draft editor state module exists", () => {
  expect(
    existsSync(
      resolve(
        process.cwd(),
        "src/features/drafts/editor-state.ts",
      ),
    ),
  ).toBe(true);
  const source = readFileSync(
    resolve(
      process.cwd(),
      "src/features/drafts/editor-state.ts",
    ),
    "utf8",
  );
  expect(source).toContain("export function issuesByNode");
  expect(source).toContain("export function issuesByPointer");
});

test("semantic edits replace one JSON pointer without mutating the fixture", () => {
  const draft = draftFixture();

  const changed = replaceAtPointer(
    draft.agent_spec,
    "/localized_metadata/name/en-US",
    "Math Agent",
  );

  expect(changed).not.toBe(draft.agent_spec);
  expect(changed.localized_metadata.name["en-US"]).toBe("Math Agent");
  expect(draft.agent_spec.localized_metadata.name["en-US"]).toBe(
    "Agent draft",
  );
});

test("layout movement marks the shared draft dirty without copying AgentSpec", () => {
  const state = initialDraftState(draftFixture());

  const changed = draftEditorReducer(state, {
    type: "move-node",
    nodeId: "source-node",
    position: {x: 24, y: 80},
  });

  expect(changed.agentSpec).toBe(state.agentSpec);
  expect(changed.layout).not.toBe(state.layout);
  expect(changed.layout.nodes[0]).toMatchObject({x: 24, y: 80});
  expect(changed.dirty).toBe(true);
});

test("save success installs the authoritative server draft", () => {
  const state = initialDraftState(draftFixture());
  const serverDraft = {
    ...draftFixture(),
    revision: 2,
    digest: "b".repeat(64),
  };

  const changed = draftEditorReducer(state, {
    type: "save-succeeded",
    draft: serverDraft,
  });

  expect(changed.serverDraft).toBe(serverDraft);
  expect(changed.agentSpec).toBe(serverDraft.agent_spec);
  expect(changed.dirty).toBe(false);
  expect(changed.saveStatus).toBe("saved");
});

test("validation issues are projected by node and exact JSON pointer", () => {
  const issues = [
    {
      code: "required",
      json_pointer: "/nodes/0/config/prompt",
      node_id: "model-node",
      message_key: "validation.required",
    },
    {
      code: "range",
      json_pointer: "/nodes/0/config/timeout_ms",
      node_id: "model-node",
      message_key: "validation.range",
    },
    {
      code: "required",
      json_pointer: "/localized_metadata/name/ru-RU",
      node_id: null,
      message_key: "validation.required",
    },
  ];

  expect(issuesByNode(issues).get("model-node")).toHaveLength(2);
  expect(issuesByNode(issues).has("null")).toBe(false);
  expect(
    issuesByPointer(issues).get("/localized_metadata/name/ru-RU")?.[0]
      ?.node_id,
  ).toBeNull();
});
