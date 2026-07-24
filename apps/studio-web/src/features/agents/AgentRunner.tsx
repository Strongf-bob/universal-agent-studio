"use client";

import { Calculator, Cpu, Fingerprint, ListTree, Play } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import {
  ApiClientError,
  type AgentVersionSummary,
  createRun,
} from "@/lib/api/client";
import { type Locale, localizedPath } from "@/lib/i18n/routing";

type Props = {
  version: AgentVersionSummary;
  locale?: Locale;
  startRun?: typeof createRun;
  onRunCreated?: (runId: string) => void;
};

export function AgentRunner({
  version,
  locale = "ru-RU",
  startRun = createRun,
  onRunCreated,
}: Props) {
  const t = useTranslations("runner");
  const errors = useTranslations("errors");
  const [question, setQuestion] = useState(t("goldenQuestion"));
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<ApiClientError | null>(null);
  const [running, setRunning] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setQuestionError(t("validation.questionRequired"));
      inputRef.current?.focus();
      return;
    }
    setQuestionError(null);
    setApiError(null);
    setRunning(true);
    try {
      const run = await startRun({version, question, locale});
      if (onRunCreated) {
        onRunCreated(run.run_id);
      } else {
        window.location.assign(
          localizedPath(locale, `/runs/${run.run_id}`),
        );
      }
    } catch (error) {
      setApiError(
        error instanceof ApiClientError
          ? error
          : new ApiClientError("unknown", null, false),
      );
    } finally {
      setRunning(false);
    }
  }

  const apiMessage = apiError
    ? errors.has(apiError.code)
      ? errors(apiError.code)
      : errors("unknown")
    : null;

  return (
    <section className="runnerGrid" aria-labelledby="runner-title">
      <div className="runnerMain">
        <header className="sectionHeader">
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1 id="runner-title">{t("title")}</h1>
          <p className="sectionDescription">{t("description")}</p>
        </header>

        <div className="versionStrip" aria-label={t("activeVersion")}>
          <div className="versionIdentity">
            <Fingerprint aria-hidden />
            <span>
              <span className="metaLabel">{t("activeVersion")}</span>
              <strong>{version.version_id}</strong>
            </span>
          </div>
          <span className="statusPill">
            <span className="statusDot" aria-hidden />
            {t("immutable")}
          </span>
          <div className="digestValue">
            <span className="metaLabel">{t("digest")}</span>
            <code>{version.digest}</code>
          </div>
        </div>

        <form className="runnerForm" noValidate onSubmit={submit}>
          <div className="fieldGroup">
            <label htmlFor="agent-question">{t("inputLabel")}</label>
            <input
              ref={inputRef}
              id="agent-question"
              value={question}
              aria-describedby="agent-question-hint agent-question-error"
              aria-invalid={Boolean(questionError)}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <p className="fieldHint" id="agent-question-hint">
              {t("inputHint")}
            </p>
            {questionError ? (
              <p className="fieldError" id="agent-question-error" role="alert">
                {questionError}
              </p>
            ) : null}
          </div>
          {apiMessage ? (
            <div className="apiError" role="alert">
              <span>{apiMessage}</span>
              {apiError?.requestId ? (
                <code>
                  {t("supportCode", {requestId: apiError.requestId})}
                </code>
              ) : null}
            </div>
          ) : null}
          <button className="buttonPrimary runButton" disabled={running}>
            <Play aria-hidden />
            {running ? t("running") : t("run")}
          </button>
        </form>
      </div>

      <aside className="runnerAside" aria-labelledby="runner-ready-title">
        <p className="metaLabel" id="runner-ready-title">
          {t("readyTitle")}
        </p>
        <ol className="executionPreview">
          <li>
            <Cpu aria-hidden />
            <span>{t("readySteps.model")}</span>
          </li>
          <li>
            <Calculator aria-hidden />
            <span>{t("readySteps.tool")}</span>
          </li>
          <li>
            <ListTree aria-hidden />
            <span>{t("readySteps.trace")}</span>
          </li>
        </ol>
      </aside>
    </section>
  );
}
