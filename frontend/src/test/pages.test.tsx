import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { Alert, Overview, Page } from "../api/types";
import { mockApi, renderPage } from "./utils";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const emptyPage = <T,>(): Page<T> => ({ items: [], page: 1, page_size: 25, total: 0 });

const overview: Overview = {
  notice: "Synthetic data. Labels are simulated fraud.",
  transactions_total: 5000,
  transactions_scored: 5000,
  transactions_unscored: 0,
  alerts_total: 12,
  alerts_by_status: { open: 10, in_review: 1, escalated: 1, closed_false_positive: 0, closed_actioned: 0 },
  open_alerts_by_priority: { low: 0, medium: 2, high: 6, critical: 4 },
  alerts_per_1000_scored: 2.4,
  cases_by_status: { open: 1, investigating: 0, pending_decision: 0, closed: 0 },
  decisions: {},
  my_open_alerts: 3,
  my_open_cases: 1,
  active_model: { id: 1, version: "hist-strict-synthetic", threshold: "0.9", is_synthetic_demo: true },
  label_check: null,
};

const alert: Alert = {
  id: 7,
  status: "open",
  priority: "critical",
  assignee: null,
  created_at: "2026-01-01T03:00:00Z",
  updated_at: "2026-01-01T03:00:00Z",
  closed_at: null,
  transaction: {
    id: 70,
    external_id: null,
    source: "csv",
    import_batch_id: 1,
    step: 4,
    occurred_at: "2026-01-01T03:00:00Z",
    type: "TRANSFER",
    amount: "181000.00",
    origin_account: "C1",
    dest_account: "C2",
    origin_balance_before: "181000.00",
    origin_balance_after: "0.00",
    dest_balance_before: "0.00",
    dest_balance_after: "0.00",
    created_at: "2026-01-01T03:00:00Z",
  },
  risk_score: "0.99812",
  reason_codes: ["MODEL_SCORE_ABOVE_THRESHOLD", "HIGH_RISK_TYPE"],
  model_version: "hist-strict-synthetic",
  case_id: null,
  case_reference: null,
};

describe("login", () => {
  it("redirects to login and shows the API's message on bad credentials", async () => {
    mockApi(
      { "POST /auth/login": () => ({ status: 401, body: { error: { code: "UNAUTHORIZED", message: "Invalid email or password", details: [], request_id: "r" } } }) },
      null,
    );
    renderPage(<App />, { route: "/alerts", signedIn: false });
    await userEvent.type(await screen.findByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password-123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("signs in and lands on the page that was requested", async () => {
    const { calls } = mockApi({
      "POST /auth/login": { access_token: "tok", token_type: "bearer", expires_in: 3600 },
      "/alerts": emptyPage<Alert>(),
    });
    renderPage(<App />, { route: "/alerts", signedIn: false });
    await userEvent.type(await screen.findByLabelText("Email"), "ana@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "right-password-123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Alert queue" })).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({ email: "ana@example.com", password: "right-password-123" });
  });
});

describe("overview", () => {
  it("shows workload counts and the synthetic-data warnings", async () => {
    mockApi({
      "/metrics/overview": overview,
      "/metrics/risk-distribution": {
        notice: "",
        model_version: "hist-strict-synthetic",
        threshold: "0.9",
        transactions: 5000,
        bins: [{ lower: 0, upper: 1, count: 5000, labelled_fraud: 108 }],
        by_level: { low: 4900, medium: 80, high: 15, critical: 5 },
        above_threshold: 12,
      },
    });
    renderPage(<App />);
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("My open alerts").previousSibling).toHaveTextContent("3");
    expect(screen.getByText("Open alerts").previousSibling).toHaveTextContent("12");
    expect(screen.getByText(/Its scores are not results/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("synthetic data");
    expect(await screen.findByRole("img", { name: "Histogram of risk scores" })).toBeInTheDocument();
  });

  it("shows an error with the request ID and retries", async () => {
    let fail = true;
    mockApi({
      "/metrics/overview": () =>
        fail ? { status: 500, body: { error: { code: "INTERNAL_ERROR", message: "An unexpected error occurred", details: [], request_id: "req-9" } } } : { body: overview },
    });
    renderPage(<App />);
    expect(await screen.findByText("Request ID: req-9")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("My open alerts")).toBeInTheDocument();
  });
});

describe("alert queue", () => {
  it("shows an empty state", async () => {
    mockApi({ "/alerts": emptyPage<Alert>() });
    renderPage(<App />, { route: "/alerts" });
    expect(await screen.findByText("No alerts match these filters")).toBeInTheDocument();
  });

  it("lists alerts and opens a case with the selected ones", async () => {
    const { calls } = mockApi({
      "/alerts": { items: [alert], page: 1, page_size: 25, total: 1 },
      "POST /cases": { id: 3, reference: "CASE-000003" },
      "/cases/3": () => ({ status: 404, body: { error: { code: "NOT_FOUND", message: "x", details: [], request_id: "r" } } }),
    });
    renderPage(<App />, { route: "/alerts" });
    expect(await screen.findByRole("link", { name: "#7" })).toBeInTheDocument();
    // The default view asks the server for the active statuses only.
    const listCall = calls.find((c) => c.path === "/alerts");
    expect(listCall).toBeDefined();
    await userEvent.click(screen.getByLabelText("Select alert 7"));
    await userEvent.click(screen.getByRole("button", { name: "Open case with selected" }));
    await userEvent.type(screen.getByLabelText("Title"), "Mule pattern");
    await userEvent.click(screen.getByRole("button", { name: "Open case" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/cases")).toBe(true));
    expect(calls.find((c) => c.method === "POST" && c.path === "/cases")?.body).toMatchObject({
      title: "Mule pattern",
      alert_ids: [7],
    });
  });

  it("requests the active statuses by default", async () => {
    const seen: string[] = [];
    mockApi({
      "/alerts": (url) => {
        seen.push(url.search);
        return { body: emptyPage<Alert>() };
      },
    });
    renderPage(<App />, { route: "/alerts" });
    await screen.findByText("No alerts match these filters");
    expect(seen[0]).toContain("status=open&status=in_review&status=escalated");
  });
});

describe("roles", () => {
  it("hides the audit log from analysts", async () => {
    mockApi({});
    renderPage(<App />, { route: "/audit" });
    expect(await screen.findByText("Senior analysts only")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit log" })).not.toBeInTheDocument();
  });
});
