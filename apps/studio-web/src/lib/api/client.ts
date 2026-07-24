import type {
  AgentSpec,
  RunTrace,
} from "@universal-agent-studio/contracts";

export type ErrorEnvelope = {
  code: string;
  message_key: string;
  retryable: boolean;
  details: Record<string, unknown>;
};

export type SessionResponse = {
  owner_id: string;
  workspace_id: string;
  project_id: string;
  preferred_locale: "ru-RU" | "en-US";
  csrf_token: string;
};

export type AgentVersionSummary = {
  version_id: string;
  agent_id: string;
  schema_version: string;
  digest: string;
  agent_spec?: AgentSpec;
};

export type CreatedRun = {
  run_id: string;
  request_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  reused: boolean;
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
