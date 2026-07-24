export type JsonObject = Record<string, unknown>;

const FORBIDDEN_SECRET_KEYS = new Set([
  "accesstoken",
  "apikey",
  "authorization",
  "authtoken",
  "bearer",
  "bearertoken",
  "clientsecret",
  "password",
  "passphrase",
  "privatekey",
  "refreshtoken",
  "secret",
  "secretkey",
  "sessiontoken",
  "token"
]);

const TERMINAL_EVENT_TYPES = new Set([
  "run.cancelled",
  "run.completed",
  "run.failed"
]);

function asObject(value: unknown): JsonObject | undefined {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as JsonObject;
  }
  return undefined;
}

function asObjects(value: unknown): JsonObject[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const object = asObject(item);
    return object === undefined ? [] : [object];
  });
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

export function findForbiddenSecretKeys(value: unknown): Set<string> {
  const errors = new Set<string>();

  if (Array.isArray(value)) {
    for (const child of value) {
      for (const error of findForbiddenSecretKeys(child)) {
        errors.add(error);
      }
    }
    return errors;
  }

  const object = asObject(value);
  if (object === undefined) {
    return errors;
  }

  for (const [key, child] of Object.entries(object)) {
    const normalizedKey = key
      .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
    if (FORBIDDEN_SECRET_KEYS.has(normalizedKey)) {
      errors.add("secret_key_forbidden");
    }
    for (const error of findForbiddenSecretKeys(child)) {
      errors.add(error);
    }
  }

  return errors;
}

export function validateAgentGraph(agent: JsonObject): Set<string> {
  const errors = new Set<string>();
  const nodes = asObjects(agent.nodes);
  const nodeIds = nodes.map((node) => asString(node.id));

  if (nodeIds.length !== new Set(nodeIds).size) {
    errors.add("duplicate_node_id");
  }

  const edges = asObjects(agent.edges);
  const edgeIds = edges.map((edge) => asString(edge.id));
  if (edgeIds.length !== new Set(edgeIds).size) {
    errors.add("duplicate_edge_id");
  }

  const modelProfileIds = new Set(
    asObjects(agent.model_profiles).map((profile) => asString(profile.id))
  );
  const toolIds = new Set(
    asObjects(agent.tools).map((tool) => asString(tool.id))
  );
  const nodesById = new Map(
    nodes.map((node) => [asString(node.id), node] as const)
  );

  for (const node of nodes) {
    for (const collectionName of ["input_ports", "output_ports"] as const) {
      const portIds = asObjects(node[collectionName]).map((port) =>
        asString(port.id)
      );
      if (portIds.length !== new Set(portIds).size) {
        errors.add("duplicate_port_id");
      }
    }

    const modelRef = asString(node.model_profile_ref);
    if (modelRef !== undefined && !modelProfileIds.has(modelRef)) {
      errors.add("dangling_model_profile_reference");
    }

    const toolRef = asString(node.tool_ref);
    if (toolRef !== undefined && !toolIds.has(toolRef)) {
      errors.add("dangling_tool_reference");
    }
  }

  for (const edge of edges) {
    for (const [endpointName, portCollection] of [
      ["source", "output_ports"],
      ["target", "input_ports"]
    ] as const) {
      const endpoint = asObject(edge[endpointName]) ?? {};
      const node = nodesById.get(asString(endpoint.node_id));
      if (node === undefined) {
        errors.add("dangling_node_reference");
        continue;
      }

      const portIds = new Set(
        asObjects(node[portCollection]).map((port) => asString(port.id))
      );
      if (!portIds.has(asString(endpoint.port_id))) {
        errors.add("dangling_port_reference");
      }
    }
  }

  return errors;
}

export function validateRunTrace(trace: JsonObject): Set<string> {
  const errors = new Set<string>();
  const events = asObjects(trace.events);

  const sequences = events.map((event) => event.sequence);
  const expectedSequences = Array.from(
    { length: events.length },
    (_, index) => index + 1
  );
  if (JSON.stringify(sequences) !== JSON.stringify(expectedSequences)) {
    errors.add("event_sequence_invalid");
  }

  const eventIds = events.map((event) => asString(event.event_id));
  if (eventIds.length !== new Set(eventIds).size) {
    errors.add("duplicate_event_id");
  }

  const runId = asString(trace.run_id);
  if (events.some((event) => asString(event.run_id) !== runId)) {
    errors.add("event_run_mismatch");
  }

  if (events.length > 0) {
    if (asString(events[0]?.type) !== "run.started") {
      errors.add("event_lifecycle_invalid");
    }
    if (!TERMINAL_EVENT_TYPES.has(asString(events.at(-1)?.type) ?? "")) {
      errors.add("event_lifecycle_invalid");
    }

    if (asString(events[0]?.causation_id) !== asString(trace.request_id)) {
      errors.add("event_causation_invalid");
    }
    for (let index = 1; index < events.length; index += 1) {
      if (
        asString(events[index]?.causation_id) !==
        asString(events[index - 1]?.event_id)
      ) {
        errors.add("event_causation_invalid");
      }
    }
  }

  const expectedTerminalType: Record<string, string> = {
    cancelled: "run.cancelled",
    completed: "run.completed",
    failed: "run.failed"
  };
  const status = asString(trace.status) ?? "";
  if (
    events.length > 0 &&
    asString(events.at(-1)?.type) !== expectedTerminalType[status]
  ) {
    errors.add("event_lifecycle_invalid");
  }

  const provenance = asObject(trace.provenance) ?? {};
  const redactionPolicyId = asString(provenance.redaction_policy_id);
  if (
    events.some(
      (event) => asString(event.redaction_policy_id) !== redactionPolicyId
    )
  ) {
    errors.add("redaction_policy_mismatch");
  }

  return errors;
}

export function semanticErrorCodes(
  schemaName: string,
  instance: JsonObject
): Set<string> {
  const errors = findForbiddenSecretKeys(instance);

  if (schemaName === "agent-spec.schema.json") {
    for (const error of validateAgentGraph(instance)) {
      errors.add(error);
    }
  } else if (schemaName === "run-trace.schema.json") {
    for (const error of validateRunTrace(instance)) {
      errors.add(error);
    }
  }

  return errors;
}
