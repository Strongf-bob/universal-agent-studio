import type {RunEvent} from "@universal-agent-studio/contracts";
import {renderHook, waitFor} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {
  mergeRunEvents,
  type RunEventConnector,
  useRunEvents,
} from "@/features/runs/useRunEvents";

import {event, runId} from "./run-fixtures";

describe("useRunEvents", () => {
  it("hydrates, resumes after the highest sequence, and removes duplicate ids", async () => {
    const first = event(1, "run.started");
    const terminal = event(2, "run.completed");
    const cursors: number[] = [];
    const connect: RunEventConnector = async function* ({afterSequence}) {
      cursors.push(afterSequence);
      yield first;
      yield terminal;
    };

    const {result} = renderHook(() =>
      useRunEvents({
        runId,
        initialEvents: [first],
        connect,
        reconnectDelayMs: 0,
      }),
    );

    await waitFor(() => expect(result.current.state).toBe("complete"));
    expect(result.current.events.map((item) => item.event_id)).toEqual([
      first.event_id,
      terminal.event_id,
    ]);
    expect(result.current.lastSequence).toBe(2);
    expect(cursors).toEqual([1]);
  });

  it("reconnects from the last persisted cursor after a transient failure", async () => {
    const first = event(1, "run.started");
    const terminal = event(2, "run.completed");
    const cursors: number[] = [];
    let attempt = 0;
    const connect: RunEventConnector = async function* ({afterSequence}) {
      cursors.push(afterSequence);
      attempt += 1;
      if (attempt === 1) {
        throw new Error("temporary disconnect");
      }
      yield terminal;
    };

    const {result} = renderHook(() =>
      useRunEvents({
        runId,
        initialEvents: [first],
        connect,
        reconnectDelayMs: 0,
      }),
    );

    await waitFor(() => expect(result.current.state).toBe("complete"));
    expect(cursors).toEqual([1, 1]);
    expect(result.current.events).toHaveLength(2);
  });
});

describe("mergeRunEvents", () => {
  it("orders out-of-order batches without mutating the existing list", () => {
    const existing = [event(1, "run.started")];
    const incoming: RunEvent[] = [
      event(3, "run.completed"),
      event(2, "node.completed", "calculator-tool"),
    ];

    expect(mergeRunEvents(existing, incoming).map((item) => item.sequence)).toEqual([
      1, 2, 3,
    ]);
    expect(existing).toHaveLength(1);
  });
});
