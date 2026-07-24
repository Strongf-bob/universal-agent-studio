#!/usr/bin/env node

import {rmSync} from "node:fs";

import {
  assertSafeStateDirectory,
  composeArguments,
  requireDocker,
  runDocker,
  stateDirectory,
} from "./local-common.mjs";

const arguments_ = process.argv.slice(2);
const confirmationIndex = arguments_.indexOf("--confirm");
const confirmation =
  confirmationIndex >= 0 ? arguments_[confirmationIndex + 1] : undefined;
const dryRun = arguments_.includes("--dry-run");

if (confirmation !== "RESET LOCAL DATA") {
  process.stderr.write(
    'Refusing reset. Pass --confirm "RESET LOCAL DATA" to remove local volumes.\n',
  );
  process.exit(2);
}

try {
  assertSafeStateDirectory({requireMarker: true});
  if (dryRun) {
    process.stdout.write(
      `Dry run: would remove Compose volumes and ${stateDirectory}.\n`,
    );
    process.exit(0);
  }
  requireDocker();
  runDocker(
    composeArguments("down", "--volumes", "--remove-orphans"),
  );
  rmSync(stateDirectory, {recursive: true, force: true});
  process.stdout.write("Local Compose volumes and generated secrets were removed.\n");
} catch (error) {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
}
