import type {
  PublicAgentView,
  PublicRunEvent,
  PublicRunView,
} from "@universal-agent-studio/contracts";

import type {Locale} from "@/lib/i18n";

export class PublicApiError extends Error {
  constructor(
    readonly status: number,
    message = "public_api_error",
  ) {
    super(message);
    this.name = "PublicApiError";
  }
}

export async function getPublicAgent(agentId: string): Promise<PublicAgentView> {
  const baseUrl =
    process.env.CONTROL_API_INTERNAL_URL ?? "http://control-api:8000";
  const response = await fetch(
    `${baseUrl}/public/v1/agents/${encodeURIComponent(agentId)}`,
    {
      cache: "no-store",
      headers: {Accept: "application/json"},
    },
  );
  if (!response.ok) {
    throw new PublicApiError(response.status);
  }
  return (await response.json()) as PublicAgentView;
}

export interface EventSubscription {
  run: PublicRunView;
  capability: string;
  lastSequence: number;
  signal: AbortSignal;
  onEvent: (event: PublicRunEvent) => void;
}

export interface PublicAgentTransport {
  create(input: Record<string, unknown>): Promise<PublicRunView>;
  events(subscription: EventSubscription): Promise<void>;
}

function publicHeaders(capability?: string): HeadersInit {
  return {
    Accept: "application/json",
    ...(capability ? {Authorization: `Bearer ${capability}`} : {}),
  };
}

async function readRun(
  statusUrl: string,
  capability: string,
  signal: AbortSignal,
): Promise<PublicRunView> {
  const response = await fetch(statusUrl, {
    cache: "no-store",
    credentials: "omit",
    headers: publicHeaders(capability),
    signal,
  });
  if (!response.ok) {
    throw new PublicApiError(response.status);
  }
  return (await response.json()) as PublicRunView;
}

function terminalEvent(run: PublicRunView, sequence: number): PublicRunEvent {
  const eventType =
    run.status === "completed"
      ? "run.completed"
      : run.status === "cancelled"
        ? "run.cancelled"
        : "run.failed";
  return {
    schema_version: "0.1.0",
    sequence,
    type: eventType,
    status: run.status as "completed" | "failed" | "cancelled",
    occurred_at: new Date().toISOString(),
    output: run.output,
    error_code: run.error_code,
  };
}

async function consumeEventStream(
  response: Response,
  onEvent: (event: PublicRunEvent) => void,
): Promise<{lastSequence: number; terminal: boolean}> {
  if (!response.body) {
    throw new PublicApiError(502, "event_stream_unavailable");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSequence = 0;
  let terminal = false;

  const consumeBlock = (block: string) => {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) {
      return;
    }
    const event = JSON.parse(data) as PublicRunEvent;
    lastSequence = Math.max(lastSequence, event.sequence);
    terminal = ["completed", "failed", "cancelled"].includes(event.status);
    onEvent(event);
  };

  while (true) {
    const {done, value} = await reader.read();
    buffer += decoder.decode(value, {stream: !done}).replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      consumeBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) {
      if (buffer.trim()) {
        consumeBlock(buffer);
      }
      return {lastSequence, terminal};
    }
  }
}

export function createPublicTransport(
  agentId: string,
  locale: Locale,
): PublicAgentTransport {
  return {
    async create(input) {
      const response = await fetch(
        `/public/v1/agents/${encodeURIComponent(agentId)}/runs`,
        {
          method: "POST",
          credentials: "omit",
          headers: {
            ...publicHeaders(),
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({input, locale}),
        },
      );
      if (!response.ok) {
        throw new PublicApiError(response.status);
      }
      return (await response.json()) as PublicRunView;
    },

    async events({run, capability, lastSequence, signal, onEvent}) {
      let cursor = lastSequence;
      for (let reconnect = 0; reconnect < 3 && !signal.aborted; reconnect += 1) {
        const response = await fetch(run.events_url, {
          cache: "no-store",
          credentials: "omit",
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${capability}`,
            "Last-Event-ID": String(cursor),
          },
          signal,
        });
        if (!response.ok) {
          throw new PublicApiError(response.status);
        }
        const stream = await consumeEventStream(response, (event) => {
          cursor = Math.max(cursor, event.sequence);
          onEvent(event);
        });
        cursor = Math.max(cursor, stream.lastSequence);
        if (stream.terminal) {
          return;
        }
        const current = await readRun(run.status_url, capability, signal);
        if (["completed", "failed", "cancelled"].includes(current.status)) {
          onEvent(terminalEvent(current, cursor + 1));
          return;
        }
      }
      throw new PublicApiError(502, "event_stream_interrupted");
    },
  };
}
