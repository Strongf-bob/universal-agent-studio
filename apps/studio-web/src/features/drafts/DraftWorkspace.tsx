"use client";

import type {
  AgentDraft,
  AgentSpec,
  RunEvent,
} from "@universal-agent-studio/contracts";
import {
  Braces,
  FlaskConical,
  PanelRight,
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
import type {KeyboardEvent} from "react";

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
  restoredNodeId?: string | null;
  restoredPanel?: string | null;
  restoredRunId?: string | null;
};

type DraftPanel = "simple" | "graph" | "inspector" | "bulk" | "test";
const DRAFT_PANELS: DraftPanel[] = [
  "simple",
  "graph",
  "inspector",
  "bulk",
  "test",
];

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
  restoredNodeId: nodeIdFromUrl = null,
  restoredPanel: panelFromUrl = null,
  restoredRunId: runIdFromUrl = null,
}: Omit<Props, "initialDraft"> & {initialDraft: AgentDraft}) {
  const t = useTranslations("draft");
  const initialSelectedNodeId = restoredNodeId(
    initialDraft.agent_spec,
    nodeIdFromUrl,
  );
  const initialRunId = restoredRunId(runIdFromUrl);
  const [state, dispatch] = useReducer(
    draftEditorReducer,
    {
      draft: initialDraft,
      selectedNodeId: initialSelectedNodeId,
      runId: initialRunId,
    },
    (initial) =>
      initialDraftState(initial.draft, {
        selectedNodeId: initial.selectedNodeId,
        runId: initial.runId,
      }),
  );
  const compactPanels = useMediaQuery("(max-width: 1023px)");
  const [activePanel, setActivePanel] = useState<DraftPanel>(
    restoredPanel(panelFromUrl),
  );
  const [testStarting, setTestStarting] = useState(false);
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
    async (
      agentSpec: AgentSpec,
      bubbleError = false,
      replaceEditorOnSuccess = false,
    ) => {
      const submittedAgentSpec = agentSpec;
      const submittedLayout = state.layout;
      dispatch({type: "save-started"});
      try {
        const saved = await persistDraft({
          agentId,
          expectedRevision: state.serverDraft.revision,
          agentSpec: submittedAgentSpec,
          layout: submittedLayout,
        });
        dispatch({
          type: "save-succeeded",
          draft: saved,
          replaceEditorOnSuccess,
          submittedAgentSpec,
          submittedLayout,
        });
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

  const selectNode = useCallback(
    (nodeId: string) => {
      dispatch({type: "select-node", nodeId});
      replaceDraftQuery({node: nodeId});
      if (compactPanels) {
        setActivePanel("inspector");
        replaceDraftQuery({panel: "inspector"});
      }
    },
    [compactPanels],
  );
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
  const choosePanel = useCallback(
    (panel: DraftPanel) => {
      setActivePanel(panel);
      replaceDraftQuery({panel});
      if (!compactPanels) {
        document.getElementById(panelAnchor(panel))?.scrollIntoView({
          block: "start",
          behavior: "smooth",
        });
      }
    },
    [compactPanels],
  );
  const panelProps = (panel: DraftPanel) => ({
    "aria-labelledby": compactPanels
      ? `draft-tab-${panel}`
      : panel === "graph"
        ? "graph-title"
        : undefined,
    hidden: compactPanels && activePanel !== panel,
    role: compactPanels ? ("tabpanel" as const) : undefined,
    tabIndex: compactPanels ? 0 : undefined,
  });
  const workbenchHidden =
    compactPanels && (activePanel === "bulk" || activePanel === "test");
  const utilityHidden =
    compactPanels &&
    activePanel !== "bulk" &&
    activePanel !== "test";
  const editorLocked = state.saveStatus === "saving" || testStarting;

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
        <nav
          className="workspaceJumps"
          aria-label={t("sections")}
          role={compactPanels ? "tablist" : undefined}
        >
          <PanelButton
            active={activePanel === "simple"}
            compact={compactPanels}
            icon={<Settings2 aria-hidden />}
            label={t("tabs.simple")}
            panel="simple"
            onSelect={choosePanel}
          />
          <PanelButton
            active={activePanel === "graph"}
            compact={compactPanels}
            icon={<Workflow aria-hidden />}
            label={t("tabs.graph")}
            panel="graph"
            onSelect={choosePanel}
          />
          <PanelButton
            active={activePanel === "inspector"}
            compact={compactPanels}
            icon={<PanelRight aria-hidden />}
            label={t("tabs.inspector")}
            panel="inspector"
            onSelect={choosePanel}
          />
          <PanelButton
            active={activePanel === "bulk"}
            compact={compactPanels}
            icon={<Braces aria-hidden />}
            label={t("tabs.bulk")}
            panel="bulk"
            onSelect={choosePanel}
          />
          <PanelButton
            active={activePanel === "test"}
            compact={compactPanels}
            icon={<FlaskConical aria-hidden />}
            label={t("tabs.test")}
            panel="test"
            onSelect={choosePanel}
          />
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
            disabled={
              !state.dirty ||
              state.saveStatus === "saving" ||
              testStarting
            }
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

      <div
        aria-busy={editorLocked}
        className="draftWorkbench"
        hidden={workbenchHidden}
        inert={editorLocked}
      >
        <div
          className="draftResponsiveShell"
          id="simple-settings"
          {...panelProps("simple")}
        >
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
          {...panelProps("graph")}
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
        <div
          className="draftResponsiveShell"
          id="node-inspector"
          {...panelProps("inspector")}
        >
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
      </div>

      <div className="draftUtilityGrid" hidden={utilityHidden}>
        <div
          className="draftResponsiveShell"
          id="bulk-editor-panel"
          inert={editorLocked}
          {...panelProps("bulk")}
        >
          <BulkDiffPanel
            agentSpec={state.agentSpec}
            key={`${state.serverDraft.revision}:${state.serverDraft.digest}`}
            revision={state.serverDraft.revision}
            onApply={(candidate) => save(candidate, true, true)}
            onPreview={(candidate) =>
              previewDraft({
                agentId,
                expectedRevision: state.serverDraft.revision,
                candidateAgentSpec: candidate,
              })
            }
          />
        </div>
        <div
          className="draftResponsiveShell"
          id="test-console-panel"
          {...panelProps("test")}
        >
          <DraftTestConsole
            agentId={agentId}
            agentSpec={state.serverDraft.agent_spec}
            connect={connectRun}
            disabled={state.dirty}
            loadTrace={loadTrace}
            locale={locale}
            revision={state.serverDraft.revision}
            runId={state.runId}
            startRun={startTestRun}
            onEvent={recordRunEvent}
            onRunStarted={(runId) => {
              dispatch({type: "run-started", runId});
              replaceDraftQuery({run: runId});
            }}
            onStartingChange={setTestStarting}
          />
        </div>
      </div>
    </div>
  );
}

function PanelButton({
  active,
  compact,
  icon,
  label,
  onSelect,
  panel,
}: {
  active: boolean;
  compact: boolean;
  icon: React.ReactNode;
  label: string;
  onSelect: (panel: DraftPanel) => void;
  panel: DraftPanel;
}) {
  return (
    <button
      aria-controls={compact ? panelElementId(panel) : undefined}
      aria-selected={compact ? active : undefined}
      id={`draft-tab-${panel}`}
      role={compact ? "tab" : undefined}
      tabIndex={compact && !active ? -1 : 0}
      type="button"
      onClick={() => onSelect(panel)}
      onKeyDown={(event) =>
        compact && handlePanelKeyDown(event, panel, onSelect)
      }
    >
      {icon}
      {label}
    </button>
  );
}

function handlePanelKeyDown(
  event: KeyboardEvent<HTMLButtonElement>,
  panel: DraftPanel,
  onSelect: (panel: DraftPanel) => void,
) {
  const currentIndex = DRAFT_PANELS.indexOf(panel);
  const nextIndex =
    event.key === "ArrowRight"
      ? (currentIndex + 1) % DRAFT_PANELS.length
      : event.key === "ArrowLeft"
        ? (currentIndex - 1 + DRAFT_PANELS.length) % DRAFT_PANELS.length
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? DRAFT_PANELS.length - 1
            : null;
  if (nextIndex === null) {
    return;
  }
  event.preventDefault();
  const nextPanel = DRAFT_PANELS[nextIndex];
  onSelect(nextPanel);
  document.getElementById(`draft-tab-${nextPanel}`)?.focus();
}

function panelElementId(panel: DraftPanel): string {
  const ids: Record<DraftPanel, string> = {
    simple: "simple-settings",
    graph: "graph-editor",
    inspector: "node-inspector",
    bulk: "bulk-editor-panel",
    test: "test-console-panel",
  };
  return ids[panel];
}

function panelAnchor(panel: DraftPanel): string {
  const anchors: Record<DraftPanel, string> = {
    simple: "simple-settings",
    graph: "graph-editor",
    inspector: "node-inspector",
    bulk: "bulk-editor",
    test: "test-console",
  };
  return anchors[panel];
}

function restoredPanel(value: string | null): DraftPanel {
  return value === "graph" ||
    value === "inspector" ||
    value === "bulk" ||
    value === "test"
    ? value
    : "simple";
}

function restoredNodeId(
  agentSpec: AgentSpec,
  value: string | null,
): string | null {
  return value && agentSpec.nodes.some((node) => node.id === value)
    ? value
    : null;
}

function restoredRunId(value: string | null): string | null {
  return value &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
    ? value
    : null;
}

function replaceDraftQuery(
  values: Partial<Record<"node" | "panel" | "run", string>>,
) {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(values)) {
    url.searchParams.set(key, value);
  }
  window.history.replaceState(
    null,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
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
