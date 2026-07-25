import {randomBytes} from "node:crypto";
import {
  chmodSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import {homedir} from "node:os";
import {dirname, join, parse, relative, resolve} from "node:path";
import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";

export const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
);
export const composeFile = join(
  repositoryRoot,
  "infra",
  "docker",
  "compose.local.yml",
);
export const stateDirectory = resolve(
  process.env.UAS_LOCAL_STATE_DIR ?? join(repositoryRoot, ".local"),
);
const defaultStateDirectory = join(repositoryRoot, ".local");
const ownershipMarker = join(stateDirectory, ".uas-local-state-owner");

const secretDefinitions = {
  UAS_DATABASE_PASSWORD_FILE: "database-password",
  UAS_EXECUTION_SIGNING_KEY_FILE: "execution-signing.key",
  UAS_SESSION_HASH_KEY_FILE: "session-hash.key",
  UAS_API_KEY_HASH_KEY_FILE: "api-key-hash.key",
  UAS_PUBLIC_CAPABILITY_KEY_FILE: "public-capability.key",
  UAS_WEBHOOK_SIGNING_KEY_FILE: "webhook-signing.key",
};

function markerContents() {
  return `${repositoryRoot}\n`;
}

export function assertSafeStateDirectory({requireMarker = false} = {}) {
  const forbidden = new Set([
    parse(stateDirectory).root,
    resolve(homedir()),
    repositoryRoot,
  ]);
  if (forbidden.has(stateDirectory)) {
    throw new Error(`Unsafe local state directory: ${stateDirectory}`);
  }
  const repositoryFromState = relative(stateDirectory, repositoryRoot);
  if (
    repositoryFromState !== "" &&
    !repositoryFromState.startsWith("..")
  ) {
    throw new Error(
      `Local state directory cannot contain the repository: ${stateDirectory}`,
    );
  }
  if (existsSync(ownershipMarker)) {
    if (readFileSync(ownershipMarker, "utf8") !== markerContents()) {
      throw new Error(`Local state ownership marker is invalid: ${stateDirectory}`);
    }
    return;
  }
  if (requireMarker) {
    throw new Error(`Local state ownership marker is missing: ${stateDirectory}`);
  }
  if (
    stateDirectory !== defaultStateDirectory &&
    existsSync(stateDirectory) &&
    readdirSync(stateDirectory).length > 0
  ) {
    throw new Error(
      `Refusing to adopt a non-empty local state directory: ${stateDirectory}`,
    );
  }
}

function writeSecret(path) {
  if (!existsSync(path)) {
    const descriptor = openSync(path, "wx", 0o600);
    try {
      writeFileSync(
        descriptor,
        `${randomBytes(48).toString("base64url")}\n`,
        {encoding: "utf8"},
      );
    } finally {
      closeSync(descriptor);
    }
  }
  chmodSync(path, 0o600);
  if (readFileSync(path).toString("utf8").trim().length < 32) {
    throw new Error(`Local secret is too short: ${path}`);
  }
}

export function prepareSecrets() {
  assertSafeStateDirectory();
  const secretsDirectory = join(stateDirectory, "secrets");
  mkdirSync(stateDirectory, {recursive: true, mode: 0o700});
  writeFileSync(ownershipMarker, markerContents(), {
    encoding: "utf8",
    mode: 0o600,
  });
  chmodSync(ownershipMarker, 0o600);
  mkdirSync(secretsDirectory, {recursive: true, mode: 0o700});
  chmodSync(secretsDirectory, 0o700);
  const environment = {};
  for (const [name, filename] of Object.entries(secretDefinitions)) {
    const path = join(secretsDirectory, filename);
    writeSecret(path);
    environment[name] = path;
  }
  return environment;
}

export function secretEnvironment({requireExisting = false} = {}) {
  const environment = {};
  for (const [name, filename] of Object.entries(secretDefinitions)) {
    const path = join(stateDirectory, "secrets", filename);
    if (requireExisting && !existsSync(path)) {
      throw new Error(`Missing local secret file: ${path}`);
    }
    environment[name] = path;
  }
  return environment;
}

export function runDocker(arguments_, {capture = false} = {}) {
  const result = spawnSync("docker", arguments_, {
    cwd: repositoryRoot,
    env: {
      ...process.env,
      ...secretEnvironment(),
    },
    encoding: "utf8",
    stdio: capture ? "pipe" : "inherit",
  });
  if (result.error) {
    throw new Error(
      "Docker is unavailable. Install or start Docker Desktop and retry.",
      {cause: result.error},
    );
  }
  if (result.status !== 0) {
    const detail = capture ? result.stderr.trim() : "";
    throw new Error(
      detail
        ? `Docker command failed: ${detail}`
        : `Docker command failed with status ${result.status}`,
    );
  }
  return result;
}

export function requireDocker() {
  runDocker(["info", "--format", "{{.ServerVersion}}"], {capture: true});
}

export function composeArguments(...arguments_) {
  return ["compose", "-f", composeFile, ...arguments_];
}
