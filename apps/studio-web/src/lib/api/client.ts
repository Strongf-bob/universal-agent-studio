import type {
  AgentDraft,
  AgentSpec,
  ApiKeyCreateRequest,
  ApiKeyCreateView,
  ApiKeyView,
  Layout,
  PublicationState,
  RunTrace,
  WebhookCreateRequest,
  WebhookCreateView,
  WebhookView,
} from "@universal-agent-studio/contracts";

export type ErrorEnvelope = {
  code: string;
  message_key: string;
  retryable: boolean;
  details: Record<string, unknown>;
};

export type SessionResponse = {
  owner: {
    login_name: string;
    preferred_locale: "ru-RU" | "en-US";
  };
  csrf_token: string;
};

export type AgentVersionSummary = {
  version_id: string;
  agent_id: string;
  schema_version: string;
  digest: string;
  agent_spec?: AgentSpec;
};

export type AgentVersionImportResult = AgentVersionSummary & {
  validation: {
    valid: boolean;
    issues: Array<{
      code: string;
      json_pointer: string;
      node_id: string | null;
      message_key: string;
    }>;
  };
  reused: boolean;
};

export type CreatedRun = {
  run_id: string;
  request_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  reused: boolean;
};

export type DraftValidationIssue = {
  code: string;
  json_pointer: string;
  node_id: string | null;
  message_key: string;
};

export type DraftDiff = {
  draft_id: string;
  revision: number;
  candidate_digest: string;
  validation: {
    valid: boolean;
    issues: DraftValidationIssue[];
  };
  operations: Array<{
    op: "add" | "remove" | "replace";
    json_pointer: string;
    before: unknown;
    after: unknown;
  }>;
};

export type RunSummary = {
  run_id: string;
  request_id: string;
  agent_version_id: string;
  agent_version_digest: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  locale: "ru-RU" | "en-US";
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  durable_execution_id: string | null;
  cancel_requested: boolean;
};

export class ApiClientError extends Error {
  constructor(
    readonly code: string,
    readonly requestId: string | null,
    readonly retryable: boolean,
    readonly details: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = "ApiClientError";
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    });
  } catch {
    throw new ApiClientError("network_error", null, true);
  }
  if (!response.ok) {
    let envelope: ErrorEnvelope | null = null;
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      envelope = null;
    }
    throw new ApiClientError(
      envelope?.code ?? "unknown",
      response.headers.get("X-Request-ID"),
      envelope?.retryable ?? false,
      envelope?.details ?? {},
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function serverRequestJson<T>(
  path: string,
  cookieHeader: string,
): Promise<T> {
  const baseUrl =
    process.env.CONTROL_API_INTERNAL_URL ?? "http://control-api:8000";
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
      Cookie: cookieHeader,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let envelope: ErrorEnvelope | null = null;
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      envelope = null;
    }
    throw new ApiClientError(
      envelope?.code ?? "unknown",
      response.headers.get("X-Request-ID"),
      envelope?.retryable ?? false,
      envelope?.details ?? {},
    );
  }
  return (await response.json()) as T;
}

export async function bootstrapOwner(input: {
  login_name: string;
  password: string;
  preferred_locale: "ru-RU" | "en-US";
}): Promise<void> {
  await requestJson<SessionResponse>("/api/v1/bootstrap/owner", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(input),
  });
}

export async function loginOwner(input: {
  login_name: string;
  password: string;
}): Promise<void> {
  await requestJson<SessionResponse>("/api/v1/session", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(input),
  });
}

export function getSession(): Promise<SessionResponse> {
  return requestJson<SessionResponse>("/api/v1/session");
}

export async function importAgentVersion(
  file: File,
): Promise<AgentVersionImportResult> {
  const session = await getSession();
  return requestJson<AgentVersionImportResult>(
    "/api/v1/agent-versions/import",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: await file.text(),
    },
  );
}

export async function activateAgentVersion(
  agentId: string,
  versionId: string,
): Promise<void> {
  let expectedPreviousVersionId: string | null = null;
  try {
    const active = await requestJson<AgentVersionSummary>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/active-version`,
    );
    if (active.version_id === versionId) {
      return;
    }
    expectedPreviousVersionId = active.version_id;
  } catch (error) {
    if (
      !(error instanceof ApiClientError) ||
      error.code !== "agent_version_not_active"
    ) {
      throw error;
    }
  }
  const session = await getSession();
  await requestJson(
    `/api/v1/agents/${encodeURIComponent(agentId)}/active-version`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        version_id: versionId,
        expected_previous_version_id: expectedPreviousVersionId,
      }),
    },
  );
}

export async function logoutOwner(): Promise<void> {
  const session = await getSession();
  await requestJson<void>("/api/v1/session", {
    method: "DELETE",
    headers: {"X-CSRF-Token": session.csrf_token},
  });
}

export async function createRun(input: {
  version: AgentVersionSummary;
  question: string;
  locale: "ru-RU" | "en-US";
}): Promise<CreatedRun> {
  const session = await getSession();
  const requestId = crypto.randomUUID();
  return requestJson<CreatedRun>("/api/v1/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": session.csrf_token,
    },
    body: JSON.stringify({
      schema_version: "0.1.0",
      request_id: requestId,
      agent_version_id: input.version.version_id,
      agent_version_digest: input.version.digest,
      idempotency_key: `browser:${requestId}`,
      input: {question: input.question},
      locale: input.locale,
    }),
  });
}

export async function createAgentDraft(
  agentId: string,
): Promise<AgentDraft> {
  const session = await getSession();
  return requestJson<AgentDraft>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/draft`,
    {
      method: "POST",
      headers: {"X-CSRF-Token": session.csrf_token},
    },
  );
}

export function getAgentDraft(agentId: string): Promise<AgentDraft> {
  return requestJson<AgentDraft>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/draft`,
  );
}

export function getAgentDraftForServer(
  agentId: string,
  cookieHeader: string,
): Promise<AgentDraft> {
  return serverRequestJson<AgentDraft>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/draft`,
    cookieHeader,
  );
}

export function getPublishingStateForServer(
  agentId: string,
  cookieHeader: string,
): Promise<PublicationState> {
  return serverRequestJson<PublicationState>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/publishing`,
    cookieHeader,
  );
}

export function getPublishingState(
  agentId: string,
): Promise<PublicationState> {
  return requestJson<PublicationState>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/publishing`,
  );
}

export async function publishAgent(input: {
  agentId: string;
  expectedDraftRevision: number;
  expectedActiveVersionId: string | null;
}): Promise<PublicationState> {
  const session = await getSession();
  return requestJson<PublicationState>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/publish`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        expected_draft_revision: input.expectedDraftRevision,
        expected_active_version_id: input.expectedActiveVersionId,
      }),
    },
  );
}

export async function rollbackAgent(input: {
  agentId: string;
  expectedActiveVersionId: string;
  targetVersionId: string;
}): Promise<PublicationState> {
  const session = await getSession();
  return requestJson<PublicationState>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/rollback`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        expected_active_version_id: input.expectedActiveVersionId,
        target_version_id: input.targetVersionId,
      }),
    },
  );
}

export async function createAgentApiKey(input: {
  agentId: string;
  request: ApiKeyCreateRequest;
}): Promise<ApiKeyCreateView> {
  const session = await getSession();
  return requestJson<ApiKeyCreateView>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/api-keys`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify(input.request),
    },
  );
}

export async function revokeAgentApiKey(input: {
  agentId: string;
  keyId: string;
}): Promise<ApiKeyView> {
  const session = await getSession();
  return requestJson<ApiKeyView>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/api-keys/${encodeURIComponent(input.keyId)}/revoke`,
    {
      method: "POST",
      headers: {"X-CSRF-Token": session.csrf_token},
    },
  );
}

export async function createAgentWebhook(input: {
  agentId: string;
  request: WebhookCreateRequest;
}): Promise<WebhookCreateView> {
  const session = await getSession();
  return requestJson<WebhookCreateView>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/webhooks`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify(input.request),
    },
  );
}

export async function revokeAgentWebhook(input: {
  agentId: string;
  subscriptionId: string;
}): Promise<WebhookView> {
  const session = await getSession();
  return requestJson<WebhookView>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/webhooks/${encodeURIComponent(input.subscriptionId)}/revoke`,
    {
      method: "POST",
      headers: {"X-CSRF-Token": session.csrf_token},
    },
  );
}

export async function updateAgentDraft(input: {
  agentId: string;
  expectedRevision: number;
  agentSpec: AgentSpec;
  layout: Layout;
}): Promise<AgentDraft> {
  const session = await getSession();
  return requestJson<AgentDraft>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/draft`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        expected_revision: input.expectedRevision,
        agent_spec: input.agentSpec,
        layout: input.layout,
      }),
    },
  );
}

export async function previewAgentDraftDiff(input: {
  agentId: string;
  expectedRevision: number;
  candidateAgentSpec: AgentSpec;
}): Promise<DraftDiff> {
  const session = await getSession();
  return requestJson<DraftDiff>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/draft/diff`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        expected_revision: input.expectedRevision,
        candidate_agent_spec: input.candidateAgentSpec,
      }),
    },
  );
}

export async function createDraftTestRun(input: {
  agentId: string;
  expectedRevision: number;
  runInput: Record<string, unknown>;
  locale: "ru-RU" | "en-US";
}): Promise<CreatedRun> {
  const session = await getSession();
  const requestId = crypto.randomUUID();
  return requestJson<CreatedRun>(
    `/api/v1/agents/${encodeURIComponent(input.agentId)}/draft/runs`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        expected_revision: input.expectedRevision,
        request_id: requestId,
        idempotency_key: `draft:${requestId}`,
        input: input.runInput,
        locale: input.locale,
      }),
    },
  );
}

export async function getActiveAgentVersion(
  agentId: string,
  cookieHeader: string,
): Promise<AgentVersionSummary> {
  return serverRequestJson<AgentVersionSummary>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/active-version`,
    cookieHeader,
  );
}

export function getRunForServer(
  runId: string,
  cookieHeader: string,
): Promise<RunSummary> {
  return serverRequestJson<RunSummary>(
    `/api/v1/runs/${encodeURIComponent(runId)}`,
    cookieHeader,
  );
}

export function getAgentVersionForServer(
  versionId: string,
  cookieHeader: string,
): Promise<AgentVersionSummary> {
  return serverRequestJson<AgentVersionSummary>(
    `/api/v1/agent-versions/${encodeURIComponent(versionId)}`,
    cookieHeader,
  );
}

export function getRunTrace(runId: string): Promise<RunTrace> {
  return requestJson<RunTrace>(
    `/api/v1/runs/${encodeURIComponent(runId)}/trace`,
  );
}

export async function cancelRun(
  runId: string,
): Promise<{run_id: string; status: "requested" | "already_terminal"}> {
  const session = await getSession();
  return requestJson(
    `/api/v1/runs/${encodeURIComponent(runId)}/cancel`,
    {
      method: "POST",
      headers: {"X-CSRF-Token": session.csrf_token},
    },
  );
}
