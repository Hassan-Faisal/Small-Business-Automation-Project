import { describe, expect, it } from "vitest";

import { api } from "./client";

describe("admin API client", () => {
  it("includes cookies on every request", () => {
    expect(api.defaults.withCredentials).toBe(true);
  });
});
