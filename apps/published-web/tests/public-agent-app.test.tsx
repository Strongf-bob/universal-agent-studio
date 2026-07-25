import {readFileSync} from "node:fs";
import {resolve} from "node:path";

import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe, expect, it, vi} from "vitest";

import {
  PublicAgentApp,
  type PublicAgentTransport,
} from "@/components/PublicAgentApp";

import {calculatorAgent, publicRun} from "./fixtures";

function completedTransport(): PublicAgentTransport {
  return {
    create: vi.fn(async () => publicRun("completed")),
    events: vi.fn(async () => undefined),
  };
}

describe("PublicAgentApp", () => {
  it("submits schema-derived input and announces the result", async () => {
    const user = userEvent.setup();
    const transport = completedTransport();

    render(
      <PublicAgentApp
        agent={calculatorAgent}
        locale="en-US"
        transport={transport}
      />,
    );
    await user.type(screen.getByLabelText("Expression"), "19 * 23");
    await user.type(screen.getByLabelText("Precision"), "2");
    await user.selectOptions(screen.getByLabelText("Format"), "decimal");
    await user.click(screen.getByLabelText("Show explanation"));
    await user.click(screen.getByRole("button", {name: "Run agent"}));

    expect(await screen.findByRole("status")).toHaveTextContent("437");
    expect(transport.create).toHaveBeenCalledWith({
      expression: "19 * 23",
      precision: 2,
      format: "decimal",
      explain: true,
    });
  });

  it("resumes a running result stream and keeps capability in memory", async () => {
    const user = userEvent.setup();
    const events = vi.fn(async ({onEvent}) => {
      onEvent({
        schema_version: "0.1.0",
        sequence: 3,
        type: "run.completed",
        status: "completed",
        occurred_at: "2026-07-25T12:00:00Z",
        output: {value: 437},
        error_code: null,
      });
    });
    const transport: PublicAgentTransport = {
      create: vi.fn(async () => publicRun("running")),
      events,
    };

    render(
      <PublicAgentApp
        agent={calculatorAgent}
        locale="en-US"
        transport={transport}
      />,
    );
    await user.type(screen.getByLabelText("Expression"), "19 * 23");
    await user.click(screen.getByRole("button", {name: "Run agent"}));

    expect(await screen.findByRole("status")).toHaveTextContent("437");
    expect(events).toHaveBeenCalledWith(
      expect.objectContaining({
        capability: expect.stringMatching(/^uascap_/),
        lastSequence: 0,
      }),
    );
    const source = readFileSync(
      resolve(process.cwd(), "src/components/PublicAgentApp.tsx"),
      "utf8",
    );
    expect(source).not.toMatch(/localStorage|sessionStorage|document\.cookie/);
  });

  it("shows a localized recoverable error and supports restart", async () => {
    const user = userEvent.setup();
    const transport: PublicAgentTransport = {
      create: vi.fn(async () => publicRun("failed")),
      events: vi.fn(async () => undefined),
    };

    render(
      <PublicAgentApp
        agent={calculatorAgent}
        locale="ru-RU"
        transport={transport}
      />,
    );
    await user.type(screen.getByLabelText("Выражение"), "19 * 23");
    await user.click(screen.getByRole("button", {name: "Запустить агента"}));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Не удалось завершить запуск",
    );
    await user.click(screen.getByRole("button", {name: "Начать заново"}));
    expect(screen.getByRole("button", {name: "Запустить агента"})).toBeEnabled();
  });
});
