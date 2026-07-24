"use client";

import type {
  AgentDraft,
  AgentSpec,
  RunEvent,
} from "@universal-agent-studio/contracts";
import {
  Braces,
  FlaskConical,
  Save,
  Settings2,
  Workflow,
} from "lucide-react";
import {useTranslations} from "next-intl";
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useState,
} from "react";

import {BulkDiffPanel} from "@/features/drafts/BulkDiffPanel";
import {DraftCanvas} from "@/features/drafts/DraftCanvas";
import {DraftGraphTable} from "@/features/drafts/DraftGraphTable";
import {DraftTestConsole} from "@/features/drafts/DraftTestConsole";
import {
  draftEditorReducer,
  initialDraftState,
} from "@/features/drafts/editor-state";
import {NodeInspector} from "@/features/drafts/NodeInspector";
import {projectDraftToFlow} from "@/features/drafts/projection";
import {SimpleSettings} from "@/features/drafts/SimpleSettings";
import type {DraftValidationIssue} from "@/features/drafts/types";
import type {RunEventConnector} from "@/features/runs/useRunEvents";
import {
  ApiClientError,
  createAgentDraft,
  createDraftTestRun,
  getRunTrace,
  previewAgentDraftDiff,
  updateAgentDraft,
} from "@/lib/api/client";
import type {Locale} from "@/lib/i18n/routing";

type Props = {
  agentId: string;
  initialDraft: AgentDraft | null;
  locale: Locale;
  createDraft?: typeof createAgentDraft;
  persistDraft?: typeof updateAgentDraft;
  previewDraft?: typeof previewAgentDraftDiff;
  startTestRun?: typeof createDraftTestRun;
  connectRun?: RunEventConnector;
  loadTrace?: typeof getRunTrace;
};

export function DraftWorkspace(props: Props) {
  if (props.initialDraft) {
    return <ReadyDraftWorkspace {...props} initialDraft={props.initialDraft} />;
  }
  return <DraftBootstrap {...props} />;
}

function DraftBootstrap({
  agentId,
  locale,
  createDraft = createAgentDraft,
  ...props
}: Props) {
  const t = useTranslations("draft");
  const [draft, setDraft] = useState<AgentDraft | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    void createDraft(agentId)
      .then((created) => {
        if (active) {
          setDraft(created);
        }
      })
      .catch(() => {
        if (active) {
          setError(true);
        }
      });
    return () => {
      active = false;
    };
  }, [agentId, createDraft]);
  if (error) {
    return <p role="alert">{t("bootstrapError")}</p>;
  }
  if (!draft) {
    return (
      <div className="workspaceLoading" role="status">
        <span className="loadingPulse" aria-hidden />
        {t("creating")}
      </div>
    );
  }
  return (
    <ReadyDraftWorkspace
      {...props}
      agentId={agentId}
      createDraft={createDraft}
      initialDraft={draft}
      locale={locale}
    />
  );
}

function ReadyDraftWorkspace({
  agentId,
  initialDraft,
  locale,
  persistDraft = updateAgentDraft,
  previewDraft = previewAgentDraftDiff,
  startTestRun,
  connectRun,
  loadTrace,
}: Omit<Props, "initialDraft"> & {initialDraft: AgentDraft}) {
  const t = useTranslations("draft");
  const [state, dispatch] = useReducer(
    draftEditorReducer,
    initialDraft,
    initialDraftState,
  );
  const projection = useMemo(
    () =>
      projectDraftToFlow(
        state.agentSpec,
        state.layout,
        locale,
        state.issues,
        state.runEvents,
      ),
    [locale, state.agentSpec, state.issues, state.layout, state.runEvents],
  );

  const save = useCallback(
    async (agentSpec: AgentSpec, bubbleError = false) => {
      dispatch({type: "save-started"});
      try {
        const saved = await persistDraft({
          agentId,
          expectedRevision: state.serverDraft.revision,
          agentSpec,
          layout: state.layout,
        });
        dispatch({type: "save-succeeded", draft: saved});
      } catch (error) {
        const code =
          error instanceof ApiClientError ? error.code : "unknown";
        dispatch({
          type: "save-failed",
          code,
          issues: extractValidationIssues(error),
        });
        if (bubbleError) {
          throw error;
        }
      }
    },
    [
      agentId,
      persistDraft,
      state.layout,
      state.serverDraft.revision,
    ],
  );

  const selectNode = useCallback((nodeId: string) => {
    dispatch({type: "select-node", nodeId});
  }, []);
  const moveNode = useCallback(
    (nodeId: string, position: {x: number; y: number}) => {
      dispatch({type: "move-node", nodeId, position});
    },
    [],
  );
  const moveNodeBy = useCallback(
    (nodeId: string, delta: {x: number; y: number}) => {
      const current = projection.nodes.find((node) => node.id === nodeId);
      if (!current) {
        return;
      }
      moveNode(nodeId, {
        x: current.position.x + delta.x,
        y: current.position.y + delta.y,
      });
    },
    [moveNode, projection.nodes],
  );
  const recordRunEvent = useCallback((event: RunEvent) => {
    dispatch({type: "run-event", event});
  }, []);

  const statusKey =
    state.saveStatus === "saving"
      ? "status.saving"
      : state.saveStatus === "conflict"
        ? "status.conflict"
        : state.saveStatus === "error"
          ? "status.error"
          : state.saveStatus === "saved"
            ? "status.saved"
            : state.dirty
              ? "status.dirty"
              : "status.ready";

  return (
    <div className="draftWorkspace">
      <header className="draftToolbar">
        <div className="draftIdentity">
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1>{state.agentSpec.localized_metadata.name[locale]}</h1>
          <span>
            <code>{agentId}</code>
            <span className="revisionBadge">
              {t("revision", {revision: state.serverDraft.revision})}
            </span>
          </span>
        </div>
        <nav className="workspaceJumps" aria-label={t("sections")}>
          <a href="#simple-settings">
            <Settings2 aria-hidden />
            {t("tabs.simple")}
          </a>
          <a href="#graph-editor">
            <Workflow aria-hidden />
            {t("tabs.graph")}
          </a>
          <a href="#bulk-editor">
            <Braces aria-hidden />
            {t("tabs.bulk")}
          </a>
          <a href="#test-console">
            <FlaskConical aria-hidden />
            {t("tabs.test")}
          </a>
        </nav>
        <div className="saveCluster">
          <span
            className={`saveStatus saveStatus--${state.saveStatus}`}
            role="status"
          >
            {t(statusKey)}
          </span>
          <button
            className="primaryButton"
            disabled={!state.dirty || state.saveStatus === "saving"}
            type="button"
            onClick={() => void save(state.agentSpec)}
          >
            <Save aria-hidden />
            {t("save")}
          </button>
        </div>
      </header>

      {state.issues.length ? (
        <ValidationSummary issues={state.issues} />
      ) : null}

      <div className="draftWorkbench">
        <div id="simple-settings">
          <SimpleSettings
            agentSpec={state.agentSpec}
            issues={state.issues}
            onEdit={(pointer, value) =>
              dispatch({type: "semantic-edit", pointer, value})
            }
          />
        </div>
        <section
          className="editorPanel graphPanel"
          id="graph-editor"
          aria-labelledby="graph-title"
        >
          <header className="editorPanelHeader">
            <p className="eyebrow">{t("graph.eyebrow")}</p>
            <h2 id="graph-title">{t("graph.title")}</h2>
            <p>{t("graph.description")}</p>
          </header>
          <DraftCanvas
            projection={projection}
            selectedNodeId={state.selectedNodeId}
            viewport={state.layout.viewport}
            onMove={moveNode}
            onSelect={selectNode}
            onViewport={(viewport) =>
              dispatch({type: "set-viewport", viewport})
            }
          />
          <DraftGraphTable
            locale={locale}
            nodes={projection.nodes}
            selectedNodeId={state.selectedNodeId}
            onMove={moveNodeBy}
            onSelect={selectNode}
          />
        </section>
        <NodeInspector
          agentSpec={state.agentSpec}
          issues={state.issues}
          locale={locale}
          selectedNodeId={state.selectedNodeId}
          onEdit={(pointer, value) =>
            dispatch({type: "semantic-edit", pointer, value})
          }
        />
      </div>

      <div className="draftUtilityGrid">
        <BulkDiffPanel
          agentSpec={state.agentSpec}
          key={`${state.serverDraft.revision}:${state.serverDraft.digest}`}
          revision={state.serverDraft.revision}
          onApply={(candidate) => save(candidate, true)}
          onPreview={(candidate) =>
            previewDraft({
              agentId,
              expectedRevision: state.serverDraft.revision,
              candidateAgentSpec: candidate,
            })
          }
        />
        <DraftTestConsole
          agentId={agentId}
          agentSpec={state.agentSpec}
          connect={connectRun}
          loadTrace={loadTrace}
          locale={locale}
          revision={state.serverDraft.revision}
          runId={state.runId}
          startRun={startTestRun}
          onEvent={recordRunEvent}
          onRunStarted={(runId) => dispatch({type: "run-started", runId})}
        />
      </div>
    </div>
  );
}

function ValidationSummary({issues}: {issues: DraftValidationIssue[]}) {
  const t = useTranslations("draft.validation");
  return (
    <aside className="validationSummary" role="alert">
      <strong>{t("summary", {count: issues.length})}</strong>
      <ul>
        {issues.map((issue, index) => (
          <li key={`${issue.json_pointer}:${issue.code}:${index}`}>
            <a
              href={
                issue.node_id
                  ? `#node-${issue.node_id}`
                  : fieldAnchor(issue.json_pointer)
              }
            >
              <code>{issue.json_pointer}</code>
              <span>
                {issue.code === "required" ? t("required") : t("invalid")}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function fieldAnchor(pointer: string): string {
  const anchors: Record<string, string> = {
    "/localized_metadata/name/ru-RU": "#draft-name-ru",
    "/localized_metadata/name/en-US": "#draft-name-en",
    "/localized_metadata/description/ru-RU": "#draft-description-ru",
    "/localized_metadata/description/en-US": "#draft-description-en",
  };
  return anchors[pointer] ?? "#simple-settings";
}

function extractValidationIssues(error: unknown): DraftValidationIssue[] {
  if (!(error instanceof ApiClientError)) {
    return [];
  }
  const validation = error.details.validation;
  if (
    typeof validation !== "object" ||
    validation === null ||
    !("issues" in validation) ||
    !Array.isArray(validation.issues)
  ) {
    return [];
  }
  return validation.issues.filter(isValidationIssue);
}

function isValidationIssue(value: unknown): value is DraftValidationIssue {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof value.code === "string" &&
    "json_pointer" in value &&
    typeof value.json_pointer === "string" &&
    "message_key" in value &&
    typeof value.message_key === "string" &&
    "node_id" in value &&
    (typeof value.node_id === "string" || value.node_id === null)
  );
}
