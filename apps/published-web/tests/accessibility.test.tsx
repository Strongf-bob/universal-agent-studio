import {render, screen} from "@testing-library/react";
import {expect, it, vi} from "vitest";

import {PublicAgentApp} from "@/components/PublicAgentApp";

import {calculatorAgent, publicRun} from "./fixtures";

it("associates every public field with a label and exposes polite status", () => {
  render(
    <PublicAgentApp
      agent={calculatorAgent}
      locale="en-US"
      transport={{
        create: vi.fn(async () => publicRun("completed")),
        events: vi.fn(async () => undefined),
      }}
    />,
  );

  expect(screen.getByLabelText("Expression")).toBeRequired();
  expect(screen.getByLabelText("Precision")).toHaveAttribute("type", "number");
  expect(screen.getByLabelText("Format")).toHaveRole("combobox");
  expect(screen.getByLabelText("Show explanation")).toHaveRole("checkbox");
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("main")).toBeInTheDocument();
});
