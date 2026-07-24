"use client";

import {CheckCircle2, FileJson2, ShieldCheck} from "lucide-react";
import {useTranslations} from "next-intl";
import {useState} from "react";

import {
  activateAgentVersion,
  ApiClientError,
  importAgentVersion,
  type AgentVersionImportResult,
} from "@/lib/api/client";
import {type Locale, localizedPath} from "@/lib/i18n/routing";

type Props = {
  locale: Locale;
  importVersion?: typeof importAgentVersion;
  activateVersion?: typeof activateAgentVersion;
  onActivated?: (agentId: string) => void;
};

export function AgentImportForm({
  locale,
  importVersion = importAgentVersion,
  activateVersion = activateAgentVersion,
  onActivated,
}: Props) {
  const t = useTranslations("agentImport");
  const errors = useTranslations("errors");
  const [file, setFile] = useState<File | null>(null);
  const [version, setVersion] = useState<AgentVersionImportResult | null>(
    null,
  );
  const [busy, setBusy] = useState<"import" | "activate" | null>(null);
  const [error, setError] = useState<ApiClientError | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError(new ApiClientError("agent_file_required", null, false));
      return;
    }
    setBusy("import");
    setError(null);
    try {
      setVersion(await importVersion(file));
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason
          : new ApiClientError("unknown", null, false),
      );
    } finally {
      setBusy(null);
    }
  }

  async function activate() {
    if (!version) {
      return;
    }
    setBusy("activate");
    setError(null);
    try {
      await activateVersion(version.agent_id, version.version_id);
      if (onActivated) {
        onActivated(version.agent_id);
      } else {
        window.location.assign(
          localizedPath(locale, `/agents/${version.agent_id}`),
        );
      }
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason
          : new ApiClientError("unknown", null, false),
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="importJourney">
      <form className="formStack" onSubmit={submit}>
        <div className="fieldGroup">
          <label htmlFor="agent-spec-file">{t("fileLabel")}</label>
          <input
            id="agent-spec-file"
            type="file"
            accept="application/json,.json"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setVersion(null);
              setError(null);
            }}
          />
          <p className="fieldHint">{t("fileHint")}</p>
        </div>
        <button
          className="buttonPrimary"
          type="submit"
          disabled={busy !== null}
        >
          <FileJson2 aria-hidden />
          {busy === "import" ? t("importing") : t("import")}
        </button>
      </form>

      {error ? (
        <div className="apiError" role="alert">
          <ShieldCheck aria-hidden />
          <span>
            {errors.has(error.code) ? errors(error.code) : errors("unknown")}
          </span>
        </div>
      ) : null}

      {version ? (
        <section className="importResult" aria-live="polite">
          <div className="importResultStatus">
            <CheckCircle2 aria-hidden />
            <div>
              <strong>{t("valid")}</strong>
              <span>{version.reused ? t("reused") : t("created")}</span>
            </div>
          </div>
          <dl className="traceValues">
            <div>
              <dt>{t("version")}</dt>
              <dd>{version.version_id}</dd>
            </div>
            <div>
              <dt>{t("digest")}</dt>
              <dd className="monoValue">{version.digest}</dd>
            </div>
          </dl>
          <button
            className="buttonPrimary"
            type="button"
            disabled={busy !== null}
            onClick={activate}
          >
            {busy === "activate" ? t("activating") : t("activate")}
          </button>
        </section>
      ) : null}
    </div>
  );
}
