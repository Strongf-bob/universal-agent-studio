import {expect, test} from "vitest";

import enMessages from "@/messages/en-US.json";
import ruMessages from "@/messages/ru-RU.json";

function recursiveKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value).flatMap(([key, item]) =>
    recursiveKeys(item, prefix ? `${prefix}.${key}` : key),
  );
}

test("Russian and English catalogs have identical recursive key sets", () => {
  expect(recursiveKeys(ruMessages).sort()).toEqual(
    recursiveKeys(enMessages).sort(),
  );
});
