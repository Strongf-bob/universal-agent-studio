import {existsSync, readFileSync} from "node:fs";
import {join} from "node:path";

import {
  composeArguments,
  runDocker,
  stateDirectory,
} from "./local-common.mjs";

const secretsDirectory = join(stateDirectory, "secrets");
const secretFiles = [
  "database-password",
  "execution-signing.key",
  "session-hash.key",
];
const secrets = secretFiles
  .map((filename) => join(secretsDirectory, filename))
  .filter((path) => existsSync(path))
  .map((path) => readFileSync(path, "utf8").trim())
  .filter(Boolean);

let logs = "";
try {
  const result = runDocker(
    composeArguments("logs", "--no-color", "--timestamps"),
    {capture: true},
  );
  logs = `${result.stdout ?? ""}${result.stderr ?? ""}`;
} catch (error) {
  logs = error instanceof Error ? error.message : String(error);
}
for (const secret of secrets) {
  logs = logs.replaceAll(secret, "[REDACTED]");
}
process.stdout.write(logs);
