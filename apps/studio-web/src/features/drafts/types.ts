import type {
  AgentDraft,
  AgentSpec,
  Layout,
  RunEvent,
} from "@universal-agent-studio/contracts";

export type DraftValidationIssue = {
  code: string;
  json_pointer: string;
  node_id: string | null;
  message_key: string;
};

export type DraftSaveStatus =
  | "idle"
  | "saving"
  | "saved"
  | "error"
  | "conflict";

export type DraftRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type DraftEditorState = {
  serverDraft: AgentDraft;
  agentSpec: AgentSpec;
  layout: Layout;
  dirty: boolean;
  selectedNodeId: string | null;
  issues: DraftValidationIssue[];
  saveStatus: DraftSaveStatus;
  errorCode: string | null;
  runId: string | null;
  runEvents: RunEvent[];
};

export type DraftEditorAction =
  | {type: "semantic-edit"; pointer: string; value: unknown}
  | {type: "move-node"; nodeId: string; position: {x: number; y: number}}
  | {type: "set-viewport"; viewport: Layout["viewport"]}
  | {type: "select-node"; nodeId: string | null}
  | {type: "save-started"}
  | {
      type: "save-succeeded";
      draft: AgentDraft;
      replaceEditorOnSuccess: boolean;
      submittedAgentSpec: AgentSpec;
      submittedLayout: Layout;
    }
  | {
      type: "save-failed";
      issues: DraftValidationIssue[];
      code: string;
    }
  | {type: "run-started"; runId: string}
  | {type: "run-event"; event: RunEvent}
  | {type: "run-reset"};
