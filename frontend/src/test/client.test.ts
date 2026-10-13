import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, buildQuery } from "../api/client";
import { allowedAlertMoves } from "../lib/roles";

afterEach(() => vi.unstubAllGlobals());

describe("buildQuery", () => {
  it("skips empty values and repeats arrays", () => {
    expect(buildQuery({ a: 1, b: "", c: undefined, d: null, status: ["open", "escalated"], f: false })).toBe(
      "?a=1&status=open&status=escalated&f=false",
    );
    expect(buildQuery({})).toBe("");
  });
});

describe("api", () => {
  it("turns the API error shape into an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ error: { code: "MODEL_NOT_AVAILABLE", message: "No active model", details: [], request_id: "abc" } }),
          { status: 503 },
        ),
      ),
    );
    const err = await api("/metrics/overview").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 503, code: "MODEL_NOT_AVAILABLE", message: "No active model", requestId: "abc" });
  });

  it("reports an unreachable backend clearly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(api("/health")).rejects.toMatchObject({ code: "NETWORK_ERROR", status: 0 });
  });
});

describe("allowedAlertMoves", () => {
  const analyst = { id: 1, role: "analyst" as const };
  const senior = { id: 2, role: "senior_analyst" as const };

  it("lets analysts work their own or unassigned alerts", () => {
    expect(allowedAlertMoves("open", analyst, null)).toContain("in_review");
    expect(allowedAlertMoves("open", analyst, 1)).toContain("escalated");
    expect(allowedAlertMoves("open", analyst, 99)).toEqual([]);
  });

  it("keeps escalations and reopening for senior analysts", () => {
    expect(allowedAlertMoves("escalated", analyst, 1)).toEqual([]);
    expect(allowedAlertMoves("closed_actioned", analyst, 1)).toEqual([]);
    expect(allowedAlertMoves("escalated", senior, 1)).toContain("closed_actioned");
    expect(allowedAlertMoves("closed_false_positive", senior, null)).toEqual(["in_review"]);
  });
});
