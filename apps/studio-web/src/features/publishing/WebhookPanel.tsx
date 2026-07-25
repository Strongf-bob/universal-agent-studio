import type {
  WebhookCreateView,
  WebhookView,
} from "@universal-agent-studio/contracts";
import {FormEvent, useState} from "react";
import {useTranslations} from "next-intl";

type Props = {
  webhooks: WebhookView[];
  busy: boolean;
  issued: WebhookCreateView | null;
  onCreate: (label: string, targetUrl: string) => Promise<void>;
  onRevoke: (subscriptionId: string) => Promise<void>;
  onDismiss: () => void;
};

export function WebhookPanel({
  webhooks,
  busy,
  issued,
  onCreate,
  onRevoke,
  onDismiss,
}: Props) {
  const t = useTranslations("publishing");
  const [label, setLabel] = useState("");
  const [targetUrl, setTargetUrl] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onCreate(label, targetUrl);
    setLabel("");
    setTargetUrl("");
  };

  const copySecret = async () => {
    if (issued && navigator.clipboard) {
      await navigator.clipboard.writeText(issued.secret);
    }
  };

  return (
    <section
      className="publishingPanel"
      aria-labelledby="webhooks-title"
      aria-label={t("webhooks.title")}
    >
      <div className="publishingPanelHeader">
        <div>
          <span className="eyebrow">{t("webhooks.eyebrow")}</span>
          <h2 id="webhooks-title">{t("webhooks.title")}</h2>
        </div>
      </div>
      <p className="panelDescription">{t("webhooks.description")}</p>

      {issued ? (
        <div className="oneTimeSecret" role="alert">
          <strong>{t("secret.webhookTitle")}</strong>
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

      <form className="stackedCreateForm" onSubmit={submit}>
        <label htmlFor="webhook-label">{t("webhooks.label")}</label>
        <input
          id="webhook-label"
          value={label}
          required
          maxLength={120}
          onChange={(event) => setLabel(event.target.value)}
        />
        <label htmlFor="webhook-url">{t("webhooks.url")}</label>
        <input
          id="webhook-url"
          value={targetUrl}
          required
          type="url"
          placeholder={t("webhooks.placeholder")}
          onChange={(event) => setTargetUrl(event.target.value)}
        />
        <button type="submit" disabled={busy}>
          {t("webhooks.create")}
        </button>
      </form>

      {webhooks.length === 0 ? (
        <p className="emptyState">{t("webhooks.empty")}</p>
      ) : (
        <ul className="credentialList">
          {webhooks.map((webhook) => (
            <li key={webhook.subscription_id}>
              <span>
                <strong>{webhook.label}</strong>
                <small>{webhook.target_url}</small>
              </span>
              {webhook.revoked_at ? (
                <span className="revokedBadge">{t("webhooks.revoked")}</span>
              ) : (
                <button
                  className="textButton textButton--danger"
                  type="button"
                  disabled={busy}
                  onClick={() => onRevoke(webhook.subscription_id)}
                >
                  {t("webhooks.revoke")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
