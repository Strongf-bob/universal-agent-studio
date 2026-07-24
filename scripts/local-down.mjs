#!/usr/bin/env node

import {
  composeArguments,
  requireDocker,
  runDocker,
} from "./local-common.mjs";

try {
  requireDocker();
  runDocker(composeArguments("down", "--remove-orphans"));
  process.stdout.write("Local services stopped; named volumes were preserved.\n");
} catch (error) {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
}
