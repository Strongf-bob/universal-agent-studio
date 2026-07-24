"use client";

import type {RunEvent} from "@universal-agent-studio/contracts";
import {useEffect, useMemo, useState} from "react";

const TERMINAL_EVENTS = new Set<RunEvent["type"]>([
  "run.completed",
  "run.failed",
  "run.cancelled",
]);

export type RunConnectionState =
  | "connecting"
  | "live"
  | "reconnecting"
  | "complete"
  | "error";

type ConnectOptions = {
  runId: string;
  afterSequence: number;
  signal: AbortSignal;
};

export type RunEventConnector = (
  options: ConnectOptions,
) => AsyncIterable<RunEvent>;

type UseRunEventsOptions = {
  runId: string;
  initialEvents?: RunEvent[];
  connect?: RunEventConnector;
  reconnectDelayMs?: number;
};

function terminal(events: RunEvent[]): boolean {
  return events.some((item) => TERMINAL_EVENTS.has(item.type));
}

export function mergeRunEvents(
  existing: RunEvent[],
  incoming: RunEvent[],
): RunEvent[] {
  const byId = new Map(existing.map((item) => [item.event_id, item]));
  for (const item of incoming) {
    if (!byId.has(item.event_id)) {
      byId.set(item.event_id, item);
    }
  }
  return [...byId.values()].sort((left, right) => {
    if (left.sequence !== right.sequence) {
      return left.sequence - right.sequence;
    }
    return left.event_id.localeCompare(right.event_id);
  });
}

function highestSequence(events: RunEvent[]): number {
  return events.reduce(
    (highest, item) => Math.max(highest, item.sequence),
    0,
  );
}

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  if (milliseconds <= 0) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timeout = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        resolve();
      },
      {once: true},
    );
  });
}

function parseEventBlock(block: string): RunEvent | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) {
    return null;
  }
  return JSON.parse(data) as RunEvent;
}

export const connectRunEventStream: RunEventConnector = async function* ({
  runId,
  afterSequence,
  signal,
}) {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/events`,
    {
      credentials: "include",
      headers: {
        Accept: "text/event-stream",
        "Last-Event-ID": String(afterSequence),
      },
      signal,
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`run_event_stream_${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const {done, value} = await reader.read();
    buffer += decoder.decode(value, {stream: !done}).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseEventBlock(block);
      if (parsed) {
        yield parsed;
      }
      boundary = buffer.indexOf("\n\n");
    }
    if (done) {
      const parsed = parseEventBlock(buffer);
      if (parsed) {
        yield parsed;
      }
      return;
    }
  }
};

export function useRunEvents({
  runId,
  initialEvents = [],
  connect = connectRunEventStream,
  reconnectDelayMs = 400,
}: UseRunEventsOptions) {
  const [events, setEvents] = useState<RunEvent[]>(() =>
    mergeRunEvents([], initialEvents),
  );
  const [state, setState] = useState<RunConnectionState>(() =>
    terminal(initialEvents) ? "complete" : "connecting",
  );

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let cursor = highestSequence(initialEvents);
    const seen = new Set(initialEvents.map((item) => item.event_id));

    async function consume() {
      if (terminal(initialEvents)) {
        setState("complete");
        return;
      }
      let attempt = 0;
      while (active && !controller.signal.aborted) {
        setState(attempt === 0 ? "connecting" : "reconnecting");
        try {
          let received = false;
          for await (const item of connect({
            runId,
            afterSequence: cursor,
            signal: controller.signal,
          })) {
            if (!active) {
              return;
            }
            received = true;
            setState("live");
            cursor = Math.max(cursor, item.sequence);
            if (!seen.has(item.event_id)) {
              seen.add(item.event_id);
              setEvents((current) => mergeRunEvents(current, [item]));
            }
            if (TERMINAL_EVENTS.has(item.type)) {
              setState("complete");
              return;
            }
          }
          attempt = received ? 1 : attempt + 1;
        } catch {
          if (controller.signal.aborted) {
            return;
          }
          attempt += 1;
          if (attempt > 8) {
            setState("error");
            return;
          }
        }
        setState("reconnecting");
        const backoff = Math.min(
          reconnectDelayMs * 2 ** Math.max(0, attempt - 1),
          5_000,
        );
        await wait(backoff, controller.signal);
      }
    }

    void consume();
    return () => {
      active = false;
      controller.abort();
    };
    // initialEvents seed state and the resume cursor for this run only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect, reconnectDelayMs, runId]);

  const lastSequence = useMemo(() => highestSequence(events), [events]);
  return {events, lastSequence, state};
}
