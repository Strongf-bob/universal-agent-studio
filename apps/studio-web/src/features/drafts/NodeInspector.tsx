"use client";

import type {
  AgentSpec,
  NodeSpec,
} from "@universal-agent-studio/contracts";
import {useTranslations} from "next-intl";

import {issuesByPointer} from "@/features/drafts/editor-state";
import {FieldErrors} from "@/features/drafts/SimpleSettings";
import type {DraftValidationIssue} from "@/features/drafts/types";
import type {Locale} from "@/lib/i18n/routing";

type Props = {
  agentSpec: AgentSpec;
  issues: DraftValidationIssue[];
  locale: Locale;
  selectedNodeId: string | null;
  onEdit: (pointer: string, value: unknown) => void;
};

export function NodeInspector({
  agentSpec,
  issues,
  locale,
  selectedNodeId,
  onEdit,
}: Props) {
  const t = useTranslations("draft");
  const nodeIndex = agentSpec.nodes.findIndex(
    (node) => node.id === selectedNodeId,
  );
  if (nodeIndex < 0) {
    return (
      <aside className="editorPanel inspectorPanel">
        <p className="eyebrow">{t("inspector.eyebrow")}</p>
        <h2>{t("inspector.title")}</h2>
        <p className="emptyState">{t("inspector.empty")}</p>
      </aside>
    );
  }
  const node = agentSpec.nodes[nodeIndex];
  const prefix = `/nodes/${nodeIndex}`;
  const byPointer = issuesByPointer(issues);

  return (
    <aside
      className="editorPanel inspectorPanel"
      aria-labelledby="inspector-title"
    >
      <header className="editorPanelHeader">
        <p className="eyebrow">{t("inspector.eyebrow")}</p>
        <h2 id="inspector-title">
          {t("inspector.nodeTitle", {
            label: node.localized_metadata.name[locale],
          })}
        </h2>
        <p>
          <code>{node.id}</code> · {t(`graph.kinds.${node.kind}`)}
        </p>
      </header>
      <div className="fieldStack">
        <InspectorText
          id="node-name-ru"
          label={t("inspector.nameRu")}
          pointer={`${prefix}/localized_metadata/name/ru-RU`}
          value={node.localized_metadata.name["ru-RU"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        <InspectorText
          id="node-name-en"
          label={t("inspector.nameEn")}
          pointer={`${prefix}/localized_metadata/name/en-US`}
          value={node.localized_metadata.name["en-US"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        {node.kind === "model" ? (
          <>
            <InspectorPrompt
              node={node}
              prefix={prefix}
              issues={byPointer}
              onEdit={onEdit}
            />
            <div className="fieldGroup">
              <label htmlFor="node-model-profile">
                {t("inspector.modelProfile")}
              </label>
              <select
                id="node-model-profile"
                value={node.model_profile_ref ?? ""}
                onChange={(event) =>
                  onEdit(`${prefix}/model_profile_ref`, event.target.value)
                }
              >
                {agentSpec.model_profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.localized_metadata.name[locale]}
                  </option>
                ))}
              </select>
            </div>
          </>
        ) : null}
        <div className="fieldGroup">
          <label htmlFor="node-timeout">{t("inspector.timeout")}</label>
          <input
            id="node-timeout"
            inputMode="numeric"
            min="1"
            type="number"
            value={node.timeout_ms}
            onChange={(event) =>
              onEdit(`${prefix}/timeout_ms`, Number(event.target.value))
            }
          />
        </div>
        <div className="fieldGroup">
          <label htmlFor="node-retries">{t("inspector.retries")}</label>
          <input
            id="node-retries"
            inputMode="numeric"
            min="1"
            type="number"
            value={node.retry_policy.max_attempts}
            onChange={(event) =>
              onEdit(
                `${prefix}/retry_policy/max_attempts`,
                Number(event.target.value),
              )
            }
          />
        </div>
      </div>
    </aside>
  );
}

function InspectorText({
  id,
  issues,
  label,
  onEdit,
  pointer,
  value,
}: {
  id: string;
  issues: Map<string, DraftValidationIssue[]>;
  label: string;
  onEdit: (pointer: string, value: unknown) => void;
  pointer: string;
  value: string;
}) {
  const fieldIssues = issues.get(pointer) ?? [];
  return (
    <div className="fieldGroup">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-describedby={fieldIssues.length ? `${id}-error` : undefined}
        aria-invalid={fieldIssues.length > 0}
        value={value}
        onChange={(event) => onEdit(pointer, event.target.value)}
      />
      <FieldErrors id={`${id}-error`} issues={fieldIssues} />
    </div>
  );
}

function InspectorPrompt({
  node,
  prefix,
  issues,
  onEdit,
}: {
  node: NodeSpec;
  prefix: string;
  issues: Map<string, DraftValidationIssue[]>;
  onEdit: (pointer: string, value: unknown) => void;
}) {
  const t = useTranslations("draft.inspector");
  const prompt = promptTemplate(node);
  const pointer = `${prefix}/config/prompt_template/en-US`;
  const fieldIssues = issues.get(pointer) ?? [];
  return (
    <div className="fieldGroup">
      <label htmlFor="node-prompt-en">{t("promptEn")}</label>
      <textarea
        id="node-prompt-en"
        aria-describedby={fieldIssues.length ? "node-prompt-en-error" : undefined}
        aria-invalid={fieldIssues.length > 0}
        rows={5}
        value={prompt["en-US"]}
        onChange={(event) => onEdit(pointer, event.target.value)}
      />
      <FieldErrors id="node-prompt-en-error" issues={fieldIssues} />
    </div>
  );
}

function promptTemplate(node: NodeSpec): {"ru-RU": string; "en-US": string} {
  const candidate = node.config.prompt_template;
  if (
    typeof candidate === "object" &&
    candidate !== null &&
    "ru-RU" in candidate &&
    "en-US" in candidate
  ) {
    return candidate as {"ru-RU": string; "en-US": string};
  }
  return {"ru-RU": "", "en-US": ""};
}
