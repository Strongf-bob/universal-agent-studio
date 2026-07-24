import {fireEvent, render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

vi.mock("@xyflow/react", () => ({
  Background: () => null,
  Controls: () => null,
  ReactFlow: ({nodes}: {nodes: Array<{id: string; data: {label: string}}>} ) => (
    <div data-testid="flow-canvas">
      {nodes.map((node) => (
        <span key={node.id}>{node.data.label}</span>
      ))}
    </div>
  ),
}));

import {RunTraceExplorer} from "@/features/runs/RunTraceExplorer";

import {
  agentSpec,
  completedTrace,
  WithMessages,
} from "./run-fixtures";

describe("RunTraceExplorer", () => {
  it("projects the immutable spec and opens the selected redacted node trace", () => {
    render(
      <WithMessages>
        <RunTraceExplorer
          agentSpec={agentSpec}
          events={completedTrace.events}
          locale="en-US"
          trace={completedTrace}
        />
      </WithMessages>,
    );

    expect(screen.getByTestId("flow-canvas")).toHaveTextContent("Request");
    expect(screen.getByTestId("flow-canvas")).toHaveTextContent("Calculator");

    fireEvent.click(
      screen.getByRole("button", {name: /inspect calculator/i}),
    );

    expect(screen.getByRole("heading", {name: "Calculator"})).toBeVisible();
    expect(screen.getByText("[REDACTED]")).toBeVisible();
    expect(screen.getByText("437")).toBeVisible();
    expect(screen.queryByText(/api[_-]?key/i)).not.toBeInTheDocument();
  });
});
