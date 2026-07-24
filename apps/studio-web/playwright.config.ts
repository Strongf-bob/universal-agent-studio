import {defineConfig, devices} from "@playwright/test";

const baseURL = process.env.UAS_E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../.local/playwright/test-results",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["line"], ["html", {outputFolder: "../../.local/playwright/report", open: "never"}]]
    : "line",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "bootstrap",
      testMatch: /setup\.fixture\.ts/,
      use: {...devices["Desktop Chrome"]},
    },
    {
      name: "chromium",
      testIgnore: /setup\.fixture\.ts/,
      dependencies: ["bootstrap"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "../../.local/playwright/auth.json",
      },
    },
  ],
});
