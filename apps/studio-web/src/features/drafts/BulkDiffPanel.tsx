"use client";

import type {AgentSpec} from "@universal-agent-studio/contracts";
import {Braces, GitCompareArrows} from "lucide-react";
import {useTranslations} from "next-intl";
import {useState} from "react";

import type {DraftDiff} from "@/lib/api/client";

type Props = {
  agentSpec: AgentSpec;
  revision: number;
  onPreview: (candidate: AgentSpec) => Promise<DraftDiff>;
  onApply: (candidate: AgentSpec) => Promise<void>;
};

export function BulkDiffPanel({
  agentSpec,
  revision,
  onPreview,
  onApply,
}: Props) {
  const t = useTranslations("draft.bulk");
  const [sourceOverride, setSourceOverride] = useState<string | null>(null);
  const source = sourceOverride ?? JSON.stringify(agentSpec, null, 2);
  const [candidate, setCandidate] = useState<AgentSpec | null>(null);
  const [diff, setDiff] = useState<DraftDiff | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function preview() {
    setBusy("preview");
    setError(null);
    setDiff(null);
    try {
      const parsed = JSON.parse(source) as AgentSpec;
      const result = await onPreview(parsed);
      setCandidate(parsed);
      setDiff(result);
    } catch {
      setCandidate(null);
      setError(t("invalidJson"));
    } finally {
      setBusy(null);
    }
  }

  async function apply() {
    if (!candidate) {
      return;
    }
    setBusy("apply");
    setError(null);
    try {
      await onApply(candidate);
      setCandidate(null);
      setDiff(null);
    } catch {
      setCandidate(null);
      setDiff(null);
      setError(t("stalePreview"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section
      className="editorPanel bulkPanel"
      data-draft-revision={revision}
      id="bulk-editor"
      aria-labelledby="bulk-title"
    >
      <header className="editorPanelHeader editorPanelHeader--row">
        <span>
          <p className="eyebrow">{t("eyebrow")}</p>
          <h2 id="bulk-title">{t("title")}</h2>
          <p>{t("description")}</p>
        </span>
        <Braces aria-hidden />
      </header>
      <div className="fieldGroup">
        <label htmlFor="bulk-json">{t("jsonLabel")}</label>
        <textarea
          className="codeEditor"
          id="bulk-json"
          rows={14}
          spellCheck={false}
          value={source}
          onChange={(event) => {
            setSourceOverride(event.target.value);
            setCandidate(null);
            setDiff(null);
            setError(null);
          }}
        />
      </div>
      <div className="panelActions">
        <button
          className="secondaryButton"
          disabled={busy !== null}
          type="button"
          onClick={() => void preview()}
        >
          <GitCompareArrows aria-hidden />
          {busy === "preview" ? t("previewing") : t("preview")}
        </button>
        <button
          className="primaryButton"
          disabled={!diff || busy !== null}
          type="button"
          onClick={() => void apply()}
        >
          {busy === "apply" ? t("applying") : t("apply")}
        </button>
      </div>
      {error ? (
        <p className="apiError" role="alert">
          {error}
        </p>
      ) : null}
      {diff ? (
        <div className="diffWrap" aria-live="polite">
          <p className="diffSummary">
            {t("changeCount", {count: diff.operations.length})}
          </p>
          {diff.operations.length ? (
            <table aria-label={t("tableLabel")} className="diffTable">
              <thead>
                <tr>
                  <th scope="col">{t("operation")}</th>
                  <th scope="col">{t("pointer")}</th>
                  <th scope="col">{t("before")}</th>
                  <th scope="col">{t("after")}</th>
                </tr>
              </thead>
              <tbody>
                {diff.operations.map((operation) => (
                  <tr
                    key={`${operation.op}:${operation.json_pointer}`}
                  >
                    <td>
                      <code>{operation.op}</code>
                    </td>
                    <th scope="row">
                      <code>{operation.json_pointer}</code>
                    </th>
                    <td>
                      <code>{compact(operation.before)}</code>
                    </td>
                    <td>
                      <code>{compact(operation.after)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="emptyState">{t("noChanges")}</p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function compact(value: unknown): string {
  const serialized = JSON.stringify(value);
  return serialized === undefined ? "—" : serialized;
}
