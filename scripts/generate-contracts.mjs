#!/usr/bin/env node

import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemaVersion = "0.1.0";
const bundle = join(
  root,
  "libs/python/agent_kernel/src/universal_agent_kernel/contracts/schemas/bundle.schema.json"
);
const target = join(root, "libs/typescript/contracts/src/generated.ts");
const nodeSchema = join(
  root,
  "contracts/schemas/v0.1.0/node-spec.schema.json"
);
const nodeTarget = join(
  root,
  "libs/typescript/contracts/src/node-spec.generated.ts"
);
const check = process.argv.includes("--check");
const header = [
  `// Generated from Universal Agent Studio JSON Schema v${schemaVersion}.`,
  "// Do not edit manually; run `pnpm generate:contracts`.",
  ""
].join("\n");

const temporary = await mkdtemp(join(tmpdir(), "uas-contracts-"));
try {
  async function compile(source, outputPath, cwd) {
    const result = spawnSync(
      "pnpm",
      [
        "--filter",
        "@universal-agent-studio/contracts",
        "exec",
        "json2ts",
        "--input",
        source,
        "--output",
        outputPath,
        "--cwd",
        cwd,
        "--unknownAny"
      ],
      { cwd: root, encoding: "utf8" }
    );
    if (result.status !== 0) {
      process.stderr.write(result.stderr || result.stdout);
      process.exit(result.status ?? 1);
    }
    return (await readFile(outputPath, "utf8")).replaceAll("\r\n", "\n");
  }

  const generatedPath = join(temporary, "generated.ts");
  const raw = await compile(bundle, generatedPath, dirname(bundle));
  const withoutLintBanner = raw.replace(/^\/\* eslint-disable \*\/\n+/, "");
  const withoutNodePlaceholder = withoutLintBanner.replace(
    /export type NodeSpec = \{\n  \[k: string\]: unknown;\n\};\n/,
    ""
  );
  const output = [
    header,
    'import type { NodeSpec } from "./node-spec.generated.js";',
    'export type { NodeSpec } from "./node-spec.generated.js";',
    "",
    withoutNodePlaceholder
  ].join("\n");

  const nodePath = join(temporary, "node-spec.generated.ts");
  const nodeRaw = await compile(nodeSchema, nodePath, dirname(nodeSchema));
  const nodeOutput = `${header}${nodeRaw.replace(
    /^\/\* eslint-disable \*\/\n+/,
    ""
  )}`;

  for (const [outputTarget, content] of [
    [target, output],
    [nodeTarget, nodeOutput]
  ]) {
    const current = await readFile(outputTarget, "utf8").catch(() => null);
    if (current === content) {
      continue;
    }
    if (check) {
      process.stderr.write(
        `generated contract drift: ${outputTarget.slice(root.length + 1)}\n`
      );
      process.exitCode = 1;
    } else {
      await writeFile(outputTarget, content, { encoding: "utf8" });
    }
  }
} finally {
  await rm(temporary, { recursive: true, force: true });
}
