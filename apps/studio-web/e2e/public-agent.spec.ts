import {expect, test} from "@playwright/test";

for (const example of [
  {
    locale: "en-US",
    title: "Calculator Agent",
    label: "Arithmetic problem",
    button: "Run agent",
  },
  {
    locale: "ru-RU",
    title: "Агент-калькулятор",
    label: "Арифметическая задача",
    button: "Запустить агента",
  },
] as const) {
  test(`published agent completes the golden run in ${example.locale}`, async ({
    page,
  }) => {
    if (example.locale === "ru-RU") {
      await page.setViewportSize({width: 390, height: 844});
    }
    const response = await page.goto(
      `/${example.locale}/agents/calculator-agent`,
    );
    expect(response?.headers()["content-security-policy"]).toContain(
      "frame-ancestors 'none'",
    );
    await expect(
      page.getByRole("heading", {name: example.title}),
    ).toBeVisible();
    await page.getByLabel(example.label).fill("What is 19 × 23?");
    await page.getByRole("button", {name: example.button}).focus();
    await expect(page.getByRole("button", {name: example.button})).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText("437");

    const browserState = await page.evaluate(() => ({
      local: JSON.stringify(localStorage),
      session: JSON.stringify(sessionStorage),
      cookies: document.cookie,
      html: document.documentElement.outerHTML,
    }));
    expect(browserState.local).toBe("{}");
    expect(browserState.session).toBe("{}");
    expect(browserState.cookies).toBe("");
    expect(browserState.html).not.toContain("uas_session");
    expect(browserState.html).not.toContain("uascap_");
  });
}
