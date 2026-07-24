"use client";

import type {AgentSpec} from "@universal-agent-studio/contracts";
import {useTranslations} from "next-intl";

import {issuesByPointer} from "@/features/drafts/editor-state";
import type {DraftValidationIssue} from "@/features/drafts/types";

type Props = {
  agentSpec: AgentSpec;
  issues: DraftValidationIssue[];
  onEdit: (pointer: string, value: unknown) => void;
};

export function SimpleSettings({agentSpec, issues, onEdit}: Props) {
  const t = useTranslations("draft");
  const byPointer = issuesByPointer(issues);
  const temperature = agentSpec.model_profiles[0]?.parameters.temperature;

  return (
    <section className="editorPanel settingsPanel" aria-labelledby="settings-title">
      <header className="editorPanelHeader">
        <p className="eyebrow">{t("settings.eyebrow")}</p>
        <h2 id="settings-title">{t("settings.title")}</h2>
        <p>{t("settings.description")}</p>
      </header>
      <div className="fieldStack">
        <TextField
          id="draft-name-ru"
          label={t("settings.nameRu")}
          pointer="/localized_metadata/name/ru-RU"
          value={agentSpec.localized_metadata.name["ru-RU"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        <TextField
          id="draft-name-en"
          label={t("settings.nameEn")}
          pointer="/localized_metadata/name/en-US"
          value={agentSpec.localized_metadata.name["en-US"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        <TextAreaField
          id="draft-description-ru"
          label={t("settings.descriptionRu")}
          pointer="/localized_metadata/description/ru-RU"
          value={agentSpec.localized_metadata.description["ru-RU"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        <TextAreaField
          id="draft-description-en"
          label={t("settings.descriptionEn")}
          pointer="/localized_metadata/description/en-US"
          value={agentSpec.localized_metadata.description["en-US"]}
          issues={byPointer}
          onEdit={onEdit}
        />
        <div className="fieldGroup">
          <label htmlFor="draft-default-locale">
            {t("settings.defaultLocale")}
          </label>
          <select
            id="draft-default-locale"
            value={agentSpec.interface.default_locale}
            onChange={(event) =>
              onEdit("/interface/default_locale", event.target.value)
            }
          >
            <option value="ru-RU">{t("settings.localeRu")}</option>
            <option value="en-US">{t("settings.localeEn")}</option>
          </select>
        </div>
        <div className="fieldGroup">
          <label htmlFor="draft-temperature">
            {t("settings.temperature")}
          </label>
          <input
            id="draft-temperature"
            disabled={temperature === undefined}
            inputMode="decimal"
            max="2"
            min="0"
            step="0.1"
            type="number"
            value={temperature ?? ""}
            onChange={(event) =>
              onEdit(
                "/model_profiles/0/parameters/temperature",
                Number(event.target.value),
              )
            }
          />
          <small>
            {temperature === undefined
              ? t("settings.noModel")
              : t("settings.temperatureHint")}
          </small>
        </div>
      </div>
    </section>
  );
}

type FieldProps = {
  id: string;
  label: string;
  pointer: string;
  value: string;
  issues: Map<string, DraftValidationIssue[]>;
  onEdit: (pointer: string, value: unknown) => void;
};

function TextField(props: FieldProps) {
  const fieldIssues = props.issues.get(props.pointer) ?? [];
  const errorId = `${props.id}-error`;
  return (
    <div className="fieldGroup">
      <label htmlFor={props.id}>{props.label}</label>
      <input
        id={props.id}
        aria-describedby={fieldIssues.length ? errorId : undefined}
        aria-invalid={fieldIssues.length > 0}
        type="text"
        value={props.value}
        onChange={(event) => props.onEdit(props.pointer, event.target.value)}
      />
      <FieldErrors id={errorId} issues={fieldIssues} />
    </div>
  );
}

function TextAreaField(props: FieldProps) {
  const fieldIssues = props.issues.get(props.pointer) ?? [];
  const errorId = `${props.id}-error`;
  return (
    <div className="fieldGroup">
      <label htmlFor={props.id}>{props.label}</label>
      <textarea
        id={props.id}
        aria-describedby={fieldIssues.length ? errorId : undefined}
        aria-invalid={fieldIssues.length > 0}
        rows={3}
        value={props.value}
        onChange={(event) => props.onEdit(props.pointer, event.target.value)}
      />
      <FieldErrors id={errorId} issues={fieldIssues} />
    </div>
  );
}

export function FieldErrors({
  id,
  issues,
}: {
  id: string;
  issues: DraftValidationIssue[];
}) {
  const t = useTranslations("draft.validation");
  if (!issues.length) {
    return null;
  }
  return (
    <span className="fieldError" id={id} role="alert">
      {issues
        .map((issue) =>
          issue.code === "required" ? t("required") : t("invalid"),
        )
        .join(" · ")}
    </span>
  );
}
