import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AgentRunner } from "@/features/agents/AgentRunner";
import { ApiClientError } from "@/lib/api/client";
import enMessages from "@/messages/en-US.json";
import ruMessages from "@/messages/ru-RU.json";

const version = {
  version_id: "calculator-agent-v1",
  agent_id: "calculator-agent",
  schema_version: "0.1.0",
  digest: "581a0bcb5036a6471e83ab89aa8efbc8aeee96898b2f0c8d4d598ed05454e00d",
};

function localized(locale: "ru-RU" | "en-US", children: ReactNode) {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "ru-RU" ? ruMessages : enMessages}
    >
      {children}
    </NextIntlClientProvider>,
  );
}

describe("AgentRunner", () => {
  it("shows the active immutable version and one primary Run action", () => {
    localized("ru-RU", <AgentRunner version={version} />);

    expect(screen.getByText("calculator-agent-v1")).toBeVisible();
    expect(screen.getByText(version.digest)).toBeVisible();
    expect(
      screen.getByLabelText("Арифметическая задача"),
    ).toHaveValue("Сколько будет 19 × 23?");
    expect(
      screen.getAllByRole("button", { name: "Запустить" }),
    ).toHaveLength(1);
  });

  it("uses complete English copy for the same runner", () => {
    localized("en-US", <AgentRunner version={version} />);

    expect(screen.getByRole("heading", { name: "Calculator agent" })).toBeVisible();
    expect(screen.getByLabelText("Arithmetic problem")).toHaveValue(
      "What is 19 × 23?",
    );
  });

  it("reports a safe translated API error with a support code", async () => {
    const user = userEvent.setup();
    const startRun = vi.fn().mockRejectedValue(
      new ApiClientError(
        "durable_execution_unavailable",
        "request-123",
        true,
      ),
    );
    localized(
      "ru-RU",
      <AgentRunner version={version} startRun={startRun} />,
    );

    await user.click(screen.getByRole("button", { name: "Запустить" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Сервис запуска временно недоступен. Попробуйте ещё раз.",
        ),
      ).toBeVisible();
    });
    expect(screen.getByText("Код поддержки: request-123")).toBeVisible();
    expect(screen.queryByText("durable_execution_unavailable")).not.toBeInTheDocument();
  });
});
