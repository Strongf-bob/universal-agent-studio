import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { OwnerSetupForm } from "@/features/auth/OwnerSetupForm";
import ruMessages from "@/messages/ru-RU.json";

function localized(children: ReactNode) {
  return render(
    <NextIntlClientProvider locale="ru-RU" messages={ruMessages}>
      {children}
    </NextIntlClientProvider>,
  );
}

describe("OwnerSetupForm", () => {
  it("shows visible labels and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    localized(<OwnerSetupForm locale="ru-RU" />);

    expect(screen.getByLabelText("Имя владельца")).toBeVisible();
    expect(screen.getByLabelText("Пароль")).toBeVisible();
    expect(screen.getByLabelText("Повторите пароль")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Создать владельца" }));

    expect(screen.getByLabelText("Имя владельца")).toHaveFocus();
    expect(screen.getAllByText("Введите имя владельца.")).toHaveLength(2);
  });

  it("explains a password mismatch next to confirmation", async () => {
    const user = userEvent.setup();
    localized(<OwnerSetupForm locale="ru-RU" />);

    await user.type(screen.getByLabelText("Имя владельца"), "owner");
    await user.type(
      screen.getByLabelText("Пароль"),
      "correct horse battery staple",
    );
    await user.type(
      screen.getByLabelText("Повторите пароль"),
      "different password",
    );
    await user.click(screen.getByRole("button", { name: "Создать владельца" }));

    expect(screen.getByText("Пароли не совпадают.")).toBeVisible();
    expect(screen.getByLabelText("Повторите пароль")).toHaveFocus();
  });

  it("disables the primary action while setup is pending", async () => {
    const user = userEvent.setup();
    let resolveSetup: (() => void) | undefined;
    const setupOwner = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSetup = resolve;
        }),
    );
    localized(
      <OwnerSetupForm
        locale="ru-RU"
        setupOwner={setupOwner}
        onComplete={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("Имя владельца"), "owner");
    await user.type(
      screen.getByLabelText("Пароль"),
      "correct horse battery staple",
    );
    await user.type(
      screen.getByLabelText("Повторите пароль"),
      "correct horse battery staple",
    );
    await user.click(screen.getByRole("button", { name: "Создать владельца" }));

    expect(screen.getByRole("button", { name: "Создаём владельца…" }))
      .toBeDisabled();
    resolveSetup?.();
    await waitFor(() => expect(setupOwner).toHaveBeenCalledOnce());
  });
});
