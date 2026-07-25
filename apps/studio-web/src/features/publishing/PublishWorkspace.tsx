"use client";

import type {
  ApiKeyCreateView,
  PublicationState,
  WebhookCreateView,
} from "@universal-agent-studio/contracts";
import {useState} from "react";
import {useTranslations} from "next-intl";

import {CredentialPanel} from "@/features/publishing/CredentialPanel";
import type {PublishingApi} from "@/features/publishing/types";
import {VersionLedger} from "@/features/publishing/VersionLedger";
import {WebhookPanel} from "@/features/publishing/WebhookPanel";
import {
  ApiClientError,
  createAgentApiKey,
  createAgentWebhook,
  getPublishingState,
  publishAgent,
  revokeAgentApiKey,
  revokeAgentWebhook,
  rollbackAgent,
} from "@/lib/api/client";
import type {Locale} from "@/lib/i18n/routing";

const defaultApi: PublishingApi = {
  refresh: getPublishingState,
  publish: publishAgent,
  rollback: rollbackAgent,
  createApiKey: createAgentApiKey,
  revokeApiKey: revokeAgentApiKey,
  createWebhook: createAgentWebhook,
  revokeWebhook: revokeAgentWebhook,
};

type Props = {
  agentId: string;
  initialState: PublicationState;
  locale: Locale;
  api?: PublishingApi;
};

type Action =
  | "idle"
  | "publishing"
  | "rolling-back"
  | "creating-key"
  | "revoking-key"
  | "creating-webhook"
  | "revoking-webhook";

function isConflict(error: unknown): boolean {
  return (
    error instanceof ApiClientError &&
    ["draft_revision_conflict", "active_version_conflict"].includes(error.code)
  );
}

export function PublishWorkspace({
  agentId,
  initialState,
  locale,
  api = defaultApi,
}: Props) {
  const t = useTranslations("publishing");
  const [state, setState] = useState(initialState);
  const [action, setAction] = useState<Action>("idle");
  const [error, setError] = useState<"conflict" | "generic" | null>(null);
  const [issuedKey, setIssuedKey] = useState<ApiKeyCreateView | null>(null);
  const [issuedWebhook, setIssuedWebhook] =
    useState<WebhookCreateView | null>(null);
  const busy = action !== "idle";

  const handleFailure = async (caught: unknown) => {
    if (isConflict(caught)) {
      setError("conflict");
      try {
        setState(await api.refresh(agentId));
      } catch {
        // The conflict remains actionable even if the refresh is unavailable.
      }
    } else {
      setError("generic");
    }
  };

  const publish = async () => {
    setAction("publishing");
    setError(null);
    try {
      setState(
        await api.publish({
          agentId,
          expectedDraftRevision: state.draft_revision,
          expectedActiveVersionId: state.active_version_id,
        }),
      );
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const rollback = async (targetVersionId: string) => {
    if (!state.active_version_id) {
      return;
    }
    setAction("rolling-back");
    setError(null);
    try {
      setState(
        await api.rollback({
          agentId,
          expectedActiveVersionId: state.active_version_id,
          targetVersionId,
        }),
      );
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const createKey = async (label: string) => {
    setAction("creating-key");
    setError(null);
    setIssuedKey(null);
    try {
      const created = await api.createApiKey({
        agentId,
        request: {
          label,
          scopes: ["runs:create", "runs:read", "events:read"],
          expires_at: null,
        },
      });
      setIssuedKey(created);
      setState((current) => ({
        ...current,
        api_keys: [
          ...current.api_keys,
          {
            key_id: created.key_id,
            label: created.label,
            prefix: created.prefix,
            scopes: created.scopes,
            expires_at: created.expires_at,
            created_at: created.created_at,
            last_used_at: created.last_used_at,
            revoked_at: created.revoked_at,
          },
        ],
      }));
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const revokeKey = async (keyId: string) => {
    setAction("revoking-key");
    setError(null);
    try {
      const revoked = await api.revokeApiKey({agentId, keyId});
      setState((current) => ({
        ...current,
        api_keys: current.api_keys.map((key) =>
          key.key_id === keyId ? revoked : key,
        ),
      }));
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const createWebhook = async (label: string, targetUrl: string) => {
    setAction("creating-webhook");
    setError(null);
    setIssuedWebhook(null);
    try {
      const created = await api.createWebhook({
        agentId,
        request: {
          label,
          target_url: targetUrl,
          events: ["run.completed", "run.failed", "run.cancelled"],
        },
      });
      setIssuedWebhook(created);
      setState((current) => ({
        ...current,
        webhooks: [
          ...current.webhooks,
          {
            subscription_id: created.subscription_id,
            label: created.label,
            target_url: created.target_url,
            events: created.events,
            created_at: created.created_at,
            revoked_at: created.revoked_at,
          },
        ],
      }));
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const revokeWebhook = async (subscriptionId: string) => {
    setAction("revoking-webhook");
    setError(null);
    try {
      const revoked = await api.revokeWebhook({agentId, subscriptionId});
      setState((current) => ({
        ...current,
        webhooks: current.webhooks.map((webhook) =>
          webhook.subscription_id === subscriptionId ? revoked : webhook,
        ),
      }));
    } catch (caught) {
      await handleFailure(caught);
    } finally {
      setAction("idle");
    }
  };

  const publicBase =
    process.env.NEXT_PUBLIC_PUBLISHED_WEB_URL ?? "http://localhost:3301";
  const publicUrl = `${publicBase}/${locale}/agents/${encodeURIComponent(agentId)}`;

  return (
    <div className="publishWorkspace">
      <header className="publishHero">
        <div>
          <span className="eyebrow">{t("eyebrow")}</span>
          <h1>{t("title")}</h1>
          <p>{t("description")}</p>
        </div>
        <div className="publishActionCard">
          <span>{t("draftRevision", {revision: state.draft_revision})}</span>
          <code>{state.draft_digest.slice(0, 16)}…</code>
          <strong>
            {t("traffic", {
              versionId: state.active_version_id ?? t("unpublished"),
            })}
          </strong>
          <button type="button" disabled={busy} onClick={publish}>
            {action === "publishing"
              ? t("publishing")
              : t("publishRevision", {revision: state.draft_revision})}
          </button>
        </div>
      </header>

      <div className="publishStatus" role="status" aria-live="polite">
        {busy ? t(`actions.${action}`) : t("actions.idle")}
      </div>
      {error ? (
        <div className="publishAlert" role="alert" tabIndex={-1}>
          <strong>
            {error === "conflict" ? t("conflict.title") : t("error.title")}
          </strong>
          <span>
            {error === "conflict"
              ? t("conflict.description")
              : t("error.description")}
          </span>
        </div>
      ) : null}

      <VersionLedger state={state} busy={busy} onRollback={rollback} />

      <section className="publishingPanel publishingPanel--wide publicDelivery">
        <div>
          <span className="eyebrow">{t("delivery.eyebrow")}</span>
          <h2>{t("delivery.title")}</h2>
          <p className="panelDescription">{t("delivery.description")}</p>
          <a href={publicUrl} target="_blank" rel="noreferrer">
            {t("delivery.open")}
          </a>
        </div>
        <pre>
          <code>{`curl -X POST 'http://localhost:8000/public/v1/agents/${agentId}/invoke' \\
  -H 'Authorization: Bearer <YOUR_API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{"locale":"${locale}","input":{"question":"19 * 23"}}'`}</code>
        </pre>
      </section>

      <div className="publishingGrid">
        <CredentialPanel
          keys={state.api_keys}
          busy={busy}
          issued={issuedKey}
          onCreate={createKey}
          onRevoke={revokeKey}
          onDismiss={() => setIssuedKey(null)}
        />
        <WebhookPanel
          webhooks={state.webhooks}
          busy={busy}
          issued={issuedWebhook}
          onCreate={createWebhook}
          onRevoke={revokeWebhook}
          onDismiss={() => setIssuedWebhook(null)}
        />
      </div>
    </div>
  );
}
