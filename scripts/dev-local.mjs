#!/usr/bin/env node

import {
  composeArguments,
  prepareSecrets,
  requireDocker,
  runDocker,
} from "./local-common.mjs";

const arguments_ = new Set(process.argv.slice(2));

try {
  if (arguments_.has("--prepare-only")) {
    prepareSecrets();
    process.stdout.write("Local secret files are ready.\n");
    process.exit(0);
  }

  requireDocker();
  prepareSecrets();
  runDocker(composeArguments("config", "-q"), {capture: true});

  if (arguments_.has("--check")) {
    process.stdout.write("Docker and the local Compose configuration are ready.\n");
    process.exit(0);
  }

  runDocker(
    composeArguments("up", "--build", "--detach", "--wait"),
  );
  process.stdout.write(
    [
      "Universal Agent Studio is ready.",
      "Studio: http://localhost:3000/ru-RU/setup",
      "Published Web App: http://localhost:3301/ru-RU/agents/calculator-agent",
      "API: http://localhost:8000/health/ready",
      "Temporal UI: http://localhost:8080",
      "",
    ].join("\n"),
  );
} catch (error) {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
}
