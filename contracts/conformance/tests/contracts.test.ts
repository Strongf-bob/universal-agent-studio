import { describe, expect, it } from "vitest";

import {
  loadFixture,
  loadManifest,
  validateFixture
} from "../src/registry.js";


const manifest = loadManifest();

describe.each(manifest.cases)("$path", (fixtureCase) => {
  it(fixtureCase.valid ? "is accepted" : "is rejected with the declared code", () => {
    const errors = validateFixture(fixtureCase);

    if (fixtureCase.valid) {
      expect(errors).toEqual([]);
    } else {
      expect(errors).toContain(fixtureCase.expected_error_code);
    }
  });
});

it("keeps the valid trace event sequence contiguous", () => {
  const trace = loadFixture("valid/run.trace.completed.json");
  const events = trace.events as Array<Record<string, unknown>>;

  expect(events.map((event) => event.sequence)).toEqual(
    Array.from({ length: events.length }, (_, index) => index + 1)
  );
});
