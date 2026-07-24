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
  agent_spec?: Record<string, unknown>;
};

export type CreatedRun = {
  run_id: string;
  request_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  reused: boolean;
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
  const baseUrl =
    process.env.CONTROL_API_INTERNAL_URL ?? "http://control-api:8000";
  const response = await fetch(
    `${baseUrl}/api/v1/agents/${encodeURIComponent(agentId)}/active-version`,
    {
      headers: {
        Accept: "application/json",
        Cookie: cookieHeader,
      },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new ApiClientError(
      "agent_version_not_active",
      response.headers.get("X-Request-ID"),
      false,
    );
  }
  return (await response.json()) as AgentVersionSummary;
}
