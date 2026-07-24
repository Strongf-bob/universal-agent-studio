import {fireEvent, render, screen} from "@testing-library/react";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {describe, expect, it, vi} from "vitest";

import {FlowTable} from "@/features/runs/FlowTable";
import {RunResult} from "@/features/runs/RunResult";
import {RunTimeline} from "@/features/runs/RunTimeline";

import {
  completedTrace,
  event,
  WithMessages,
} from "./run-fixtures";

describe("run accessibility", () => {
  it("announces reconnect state and exposes cancellation as a real button", () => {
    const onCancel = vi.fn();
    render(
      <WithMessages>
        <RunTimeline
          canCancel
          cancelling={false}
          connectionState="reconnecting"
          events={[event(1, "run.started")]}
          onCancel={onCancel}
        />
      </WithMessages>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting");
    const cancel = screen.getByRole("button", {name: "Cancel run"});
    expect(cancel).toBeEnabled();
    fireEvent.click(cancel);
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("offers a keyboard-operable table equivalent to the visual graph", () => {
    render(
      <WithMessages>
        <FlowTable
          nodes={[
            {
              id: "calculator-tool",
              kind: "tool",
              label: "Calculator",
              status: "completed",
            },
          ]}
          onSelect={vi.fn()}
          selectedNodeId={null}
        />
      </WithMessages>,
    );

    expect(
      screen.getByRole("table", {name: "Agent execution nodes"}),
    ).toBeVisible();
    expect(
      screen.getByRole("button", {name: "Inspect Calculator"}),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("announces the terminal result and keeps both locale catalogs complete", () => {
    const {rerender} = render(
      <WithMessages>
        <RunResult trace={completedTrace} loading={false} error={false} />
      </WithMessages>,
    );

    expect(
      screen.getByRole("heading", {name: "Execution completed"}),
    ).toBeVisible();
    expect(screen.getByText('{"value":437}')).toBeVisible();

    rerender(
      <WithMessages locale="ru-RU">
        <FlowTable
          nodes={[
            {
              id: "calculator-tool",
              kind: "tool",
              label: "Калькулятор",
              status: "completed",
            },
          ]}
          onSelect={vi.fn()}
          selectedNodeId={null}
        />
      </WithMessages>,
    );
    expect(
      screen.getByRole("table", {name: "Узлы выполнения агента"}),
    ).toBeVisible();
  });

  it("disables continuous motion for reduced-motion users", () => {
    const css = readFileSync(
      resolve(process.cwd(), "src/app/globals.css"),
      "utf8",
    );
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("animation-duration: 0.01ms !important");
  });
});
