import type {AgentDraft} from "@universal-agent-studio/contracts";

import type {
  DraftEditorAction,
  DraftEditorState,
  DraftValidationIssue,
} from "@/features/drafts/types";

export function initialDraftState(draft: AgentDraft): DraftEditorState {
  return {
    serverDraft: draft,
    agentSpec: draft.agent_spec,
    layout: draft.layout,
    dirty: false,
    selectedNodeId: null,
    issues: [],
    saveStatus: "idle",
    errorCode: null,
    runId: null,
    runEvents: [],
  };
}

export function draftEditorReducer(
  state: DraftEditorState,
  action: DraftEditorAction,
): DraftEditorState {
  switch (action.type) {
    case "semantic-edit":
      return {
        ...state,
        agentSpec: replaceAtPointer(
          state.agentSpec,
          action.pointer,
          action.value,
        ),
        dirty: true,
        issues: state.issues.filter(
          (issue) => issue.json_pointer !== action.pointer,
        ),
        saveStatus: "idle",
        errorCode: null,
      };
    case "move-node":
      return {
        ...state,
        layout: {
          ...state.layout,
          nodes: state.layout.nodes.map((node) =>
            node.node_id === action.nodeId
              ? {...node, ...action.position}
              : node,
          ),
        },
        dirty: true,
        saveStatus: "idle",
        errorCode: null,
      };
    case "set-viewport":
      return {
        ...state,
        layout: {...state.layout, viewport: action.viewport},
        dirty: true,
        saveStatus: "idle",
        errorCode: null,
      };
    case "select-node":
      return {...state, selectedNodeId: action.nodeId};
    case "save-started":
      return {...state, saveStatus: "saving", errorCode: null};
    case "save-succeeded":
      return {
        ...state,
        serverDraft: action.draft,
        agentSpec: action.draft.agent_spec,
        layout: action.draft.layout,
        dirty: false,
        issues: [],
        saveStatus: "saved",
        errorCode: null,
      };
    case "save-failed":
      return {
        ...state,
        issues: action.issues,
        saveStatus:
          action.code === "agent_draft_revision_conflict"
            ? "conflict"
            : "error",
        errorCode: action.code,
      };
    case "run-started":
      return {
        ...state,
        runId: action.runId,
        runEvents: [],
      };
    case "run-event": {
      const byId = new Map(
        state.runEvents.map((event) => [event.event_id, event]),
      );
      byId.set(action.event.event_id, action.event);
      return {
        ...state,
        runEvents: [...byId.values()].sort(
          (left, right) => left.sequence - right.sequence,
        ),
      };
    }
    case "run-reset":
      return {...state, runId: null, runEvents: []};
  }
}

export function replaceAtPointer<T>(
  value: T,
  pointer: string,
  replacement: unknown,
): T {
  if (pointer === "") {
    return replacement as T;
  }
  if (!pointer.startsWith("/")) {
    throw new Error("json_pointer_invalid");
  }
  const clone = structuredClone(value);
  const parts = pointer
    .slice(1)
    .split("/")
    .map((part) => part.replaceAll("~1", "/").replaceAll("~0", "~"));
  let current: unknown = clone;
  for (const part of parts.slice(0, -1)) {
    if (Array.isArray(current)) {
      current = current[Number(part)];
    } else if (isRecord(current)) {
      current = current[part];
    } else {
      throw new Error("json_pointer_not_found");
    }
  }
  const finalPart = parts.at(-1);
  if (finalPart === undefined) {
    return replacement as T;
  }
  if (Array.isArray(current)) {
    current[Number(finalPart)] = replacement;
  } else if (isRecord(current)) {
    current[finalPart] = replacement;
  } else {
    throw new Error("json_pointer_not_found");
  }
  return clone;
}

export function issuesByNode(
  issues: DraftValidationIssue[],
): Map<string, DraftValidationIssue[]> {
  return groupIssues(issues, (issue) => issue.node_id);
}

export function issuesByPointer(
  issues: DraftValidationIssue[],
): Map<string, DraftValidationIssue[]> {
  return groupIssues(issues, (issue) => issue.json_pointer);
}

function groupIssues(
  issues: DraftValidationIssue[],
  keyFor: (issue: DraftValidationIssue) => string | null,
): Map<string, DraftValidationIssue[]> {
  const grouped = new Map<string, DraftValidationIssue[]>();
  for (const issue of issues) {
    const key = keyFor(issue);
    if (key === null) {
      continue;
    }
    grouped.set(key, [...(grouped.get(key) ?? []), issue]);
  }
  return grouped;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
