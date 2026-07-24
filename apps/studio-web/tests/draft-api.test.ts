import {readFileSync} from "node:fs";
import {resolve} from "node:path";

import {expect, test} from "vitest";

test("typed draft API client surface is available", () => {
  const source = readFileSync(
    resolve(process.cwd(), "src/lib/api/client.ts"),
    "utf8",
  );

  expect(source).toContain("export async function createAgentDraft");
  expect(source).toContain("export async function updateAgentDraft");
  expect(source).toContain("export async function previewAgentDraftDiff");
  expect(source).toContain("export async function createDraftTestRun");
});
