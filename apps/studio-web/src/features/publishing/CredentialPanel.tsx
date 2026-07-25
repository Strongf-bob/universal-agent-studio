import type {
  ApiKeyCreateView,
  ApiKeyView,
} from "@universal-agent-studio/contracts";
import {FormEvent, useState} from "react";
import {useTranslations} from "next-intl";

type Props = {
  keys: ApiKeyView[];
  busy: boolean;
  issued: ApiKeyCreateView | null;
  onCreate: (label: string) => Promise<void>;
  onRevoke: (keyId: string) => Promise<void>;
  onDismiss: () => void;
};

export function CredentialPanel({
  keys,
  busy,
  issued,
  onCreate,
  onRevoke,
  onDismiss,
}: Props) {
  const t = useTranslations("publishing");
  const [label, setLabel] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onCreate(label);
    setLabel("");
  };

  const copySecret = async () => {
    if (issued && navigator.clipboard) {
      await navigator.clipboard.writeText(issued.secret);
    }
  };

  return (
    <section
      className="publishingPanel"
      aria-labelledby="api-keys-title"
      aria-label={t("keys.title")}
    >
      <div className="publishingPanelHeader">
        <div>
          <span className="eyebrow">{t("keys.eyebrow")}</span>
          <h2 id="api-keys-title">{t("keys.title")}</h2>
        </div>
      </div>
      <p className="panelDescription">{t("keys.description")}</p>

      {issued ? (
        <div className="oneTimeSecret" role="alert">
          <strong>{t("secret.title")}</strong>
          <p>{t("secret.description")}</p>
          <code>{issued.secret}</code>
          <div className="secretActions">
            <button type="button" onClick={copySecret}>
              {t("secret.copy")}
            </button>
            <button type="button" onClick={onDismiss}>
              {t("secret.dismiss")}
            </button>
          </div>
        </div>
      ) : null}

      <form className="inlineCreateForm" onSubmit={submit}>
        <label htmlFor="api-key-label">{t("keys.label")}</label>
        <div>
          <input
            id="api-key-label"
            value={label}
            required
            maxLength={120}
            onChange={(event) => setLabel(event.target.value)}
          />
          <button type="submit" disabled={busy}>
            {t("keys.create")}
          </button>
        </div>
      </form>

      {keys.length === 0 ? (
        <p className="emptyState">{t("keys.empty")}</p>
      ) : (
        <ul className="credentialList">
          {keys.map((key) => (
            <li key={key.key_id}>
              <span>
                <strong>{key.label}</strong>
                <code>{key.prefix}…</code>
              </span>
              {key.revoked_at ? (
                <span className="revokedBadge">{t("keys.revoked")}</span>
              ) : (
                <button
                  className="textButton textButton--danger"
                  type="button"
                  disabled={busy}
                  onClick={() => onRevoke(key.key_id)}
                >
                  {t("keys.revoke")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
