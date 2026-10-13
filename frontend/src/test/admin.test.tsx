import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { ImportBatch, User } from "../api/types";
import { analyst, mockApi, renderPage } from "./utils";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const senior: User = { ...analyst, id: 2, email: "sam@example.com", full_name: "Sam Senior", role: "senior_analyst" };
const admin: User = { ...analyst, id: 3, email: "ada@example.com", full_name: "Ada Admin", role: "admin" };

const batch: ImportBatch = {
  id: 4,
  filename: "march.csv",
  file_sha256: "a".repeat(64),
  uploaded_by_id: 2,
  status: "completed_with_errors",
  rows_total: 3,
  rows_inserted: 1,
  rows_duplicate: 1,
  rows_rejected: 1,
  errors: [{ row: 3, errors: ["amount: must be positive"] }],
  errors_truncated: false,
  created_at: "2026-10-13T06:00:00Z",
};

describe("imports", () => {
  it("lets a senior analyst upload a CSV and shows the row problems", async () => {
    const { calls } = mockApi(
      {
        "GET /imports": { items: [], page: 1, page_size: 20, total: 0 },
        "POST /imports": batch,
      },
      senior,
    );
    renderPage(<App />, { route: "/imports" });
    const input = await screen.findByLabelText("CSV file");
    await userEvent.upload(input, new File(["step,type\n"], "march.csv", { type: "text/csv" }));
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByText("amount: must be positive")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path === "/imports");
    expect((post?.body as { file: File }).file.name).toBe("march.csv");
  });

  it("shows analysts the history without an upload form", async () => {
    mockApi({ "GET /imports": { items: [batch], page: 1, page_size: 20, total: 1 } });
    renderPage(<App />, { route: "/imports" });
    expect(await screen.findByText("march.csv")).toBeInTheDocument();
    expect(screen.queryByLabelText("CSV file")).not.toBeInTheDocument();
  });

  it("refuses a file over the size limit before uploading", async () => {
    const { calls } = mockApi({ "GET /imports": { items: [], page: 1, page_size: 20, total: 0 } }, senior);
    renderPage(<App />, { route: "/imports" });
    const big = new File(["x"], "big.csv", { type: "text/csv" });
    Object.defineProperty(big, "size", { value: 51 * 1024 * 1024 });
    await userEvent.upload(await screen.findByLabelText("CSV file"), big);
    expect(screen.getByText(/over 50 MB/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import" })).toBeDisabled();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
});

describe("users", () => {
  it("is for admins only", async () => {
    mockApi({}, senior);
    renderPage(<App />, { route: "/users" });
    expect(await screen.findByText("Admins only")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
  });

  it("creates a user and changes another user's role", async () => {
    const { calls } = mockApi(
      {
        "GET /users": { items: [admin, analyst], page: 1, page_size: 25, total: 2 },
        "POST /users": { ...analyst, id: 9 },
        "PATCH /users/1": { ...analyst, role: "senior_analyst" },
      },
      admin,
    );
    renderPage(<App />, { route: "/users" });
    expect(await screen.findByRole("link", { name: "Users" })).toBeInTheDocument();
    // Admins cannot demote or deactivate themselves (the API refuses it too).
    expect(await screen.findByLabelText("Role for Ada Admin")).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Role for Ana Analyst"), "senior_analyst");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ role: "senior_analyst" }));

    await userEvent.click(screen.getByRole("button", { name: "New user" }));
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Full name"), "New Person");
    await userEvent.type(screen.getByLabelText(/Initial password/), "a-long-password-1");
    await userEvent.click(screen.getByRole("button", { name: "Create user" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST" && c.path === "/users")?.body).toEqual({
        email: "new@example.com",
        full_name: "New Person",
        role: "analyst",
        password: "a-long-password-1",
      }),
    );
  });
});
