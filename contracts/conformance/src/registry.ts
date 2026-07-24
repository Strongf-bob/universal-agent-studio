import {
  readFileSync,
  readdirSync
} from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { Ajv2020 } from "ajv/dist/2020.js";
import type { FormatsPlugin } from "ajv-formats";

import {
  type JsonObject,
  semanticErrorCodes
} from "./invariants.js";


export interface ContractCase {
  path: string;
  schema: string;
  valid: boolean;
  expected_error_code?: string;
}

export interface ContractManifest {
  schema_version: string;
  cases: ContractCase[];
}

const REPOSITORY_ROOT = fileURLToPath(new URL("../../..", import.meta.url));
const SCHEMA_DIR = join(
  REPOSITORY_ROOT,
  "contracts",
  "schemas",
  "v0.1.0"
);
const EXAMPLE_DIR = join(
  REPOSITORY_ROOT,
  "contracts",
  "examples",
  "v0.1.0"
);
const SCHEMA_BASE = "https://schemas.universal-agent.studio/v0.1.0/";
const require = createRequire(import.meta.url);
const addFormats = require("ajv-formats") as FormatsPlugin;

function readJson(path: string): JsonObject {
  return JSON.parse(readFileSync(path, "utf8")) as JsonObject;
}

function createValidator(): Ajv2020 {
  const ajv = new Ajv2020({
    allErrors: true,
    strict: true
  });
  addFormats(ajv);

  for (const filename of readdirSync(SCHEMA_DIR)
    .filter((value) => value.endsWith(".schema.json"))
    .sort()) {
    ajv.addSchema(readJson(join(SCHEMA_DIR, filename)));
  }

  return ajv;
}

export function loadManifest(): ContractManifest {
  return readJson(join(EXAMPLE_DIR, "manifest.json")) as unknown as ContractManifest;
}

export function loadFixture(relativePath: string): JsonObject {
  return readJson(join(EXAMPLE_DIR, relativePath));
}

export function validateFixture(fixtureCase: ContractCase): string[] {
  const instance = loadFixture(fixtureCase.path);
  const validator = createValidator().getSchema(
    `${SCHEMA_BASE}${fixtureCase.schema}`
  );
  if (validator === undefined) {
    throw new Error(`Schema not registered: ${fixtureCase.schema}`);
  }

  const errors = semanticErrorCodes(fixtureCase.schema, instance);
  if (!validator(instance)) {
    errors.add("schema_validation_failed");
  }

  return [...errors].sort();
}
