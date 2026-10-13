import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Page, Role, User } from "../api/types";
import { useUser } from "../auth/AuthContext";
import { Pagination } from "../components/Pagination";
import { Empty, ErrorState, InlineError, Loading } from "../components/States";
import { formatDateTime, humanize } from "../lib/format";
import { useSearchState } from "../lib/useSearchState";

const PAGE_SIZE = 25;
const ROLES: Role[] = ["analyst", "senior_analyst", "admin"];
const MIN_PASSWORD = 12; // Same rule as the API (backend/app/schemas/user.py).

function NewUserForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const [password, setPassword] = useState("");
  const create = useMutation({
    mutationFn: () => api<User>("/users", { method: "POST", body: { email: email.trim(), full_name: fullName.trim(), role, password } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      onDone();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h2>New user</h2>
      <label>
        Email
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Full name
        <input required maxLength={120} value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </label>
      <label>
        Role
        <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {humanize(r)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Initial password
        <input
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <span className="muted small">At least {MIN_PASSWORD} characters. Share it with the person privately.</span>
      </label>
      <InlineError error={create.error} />
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          Create user
        </button>
        <button type="button" className="btn" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function PasswordReset({ user, onDone }: { user: User; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const reset = useMutation({
    mutationFn: () => api<User>(`/users/${user.id}`, { method: "PATCH", body: { password } }),
    onSuccess: onDone,
  });
  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        reset.mutate();
      }}
    >
      <label className="inline">
        New password for {user.full_name}
        <input
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <button type="submit" className="btn btn-small btn-primary" disabled={reset.isPending}>
        Set password
      </button>
      <button type="button" className="btn btn-small" onClick={onDone}>
        Cancel
      </button>
      <InlineError error={reset.error} />
    </form>
  );
}

function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const queryClient = useQueryClient();
  const [resetting, setResetting] = useState(false);
  const [saved, setSaved] = useState(false);
  const patch = useMutation({
    mutationFn: (body: Partial<Pick<User, "role" | "is_active">>) => api<User>(`/users/${user.id}`, { method: "PATCH", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
  const lockedReason = isSelf ? "You cannot change your own role or deactivate yourself" : undefined;

  return (
    <>
      <tr className={user.is_active ? undefined : "muted"}>
        <td>
          <strong>{user.full_name}</strong>
          {isSelf && <span className="muted small"> (you)</span>}
          <div className="muted small">{user.email}</div>
        </td>
        <td>
          <select
            aria-label={`Role for ${user.full_name}`}
            value={user.role}
            disabled={isSelf || patch.isPending}
            title={lockedReason}
            onChange={(e) => patch.mutate({ role: e.target.value as Role })}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {humanize(r)}
              </option>
            ))}
          </select>
        </td>
        <td>
          <span className={`badge ${user.is_active ? "status-active" : "status-inactive"}`}>{user.is_active ? "Active" : "Deactivated"}</span>
        </td>
        <td className="nowrap">{formatDateTime(user.last_login_at)}</td>
        <td className="nowrap">{formatDateTime(user.created_at)}</td>
        <td>
          <div className="actions">
            <button
              type="button"
              className="btn btn-small"
              disabled={isSelf || patch.isPending}
              title={lockedReason}
              onClick={() => patch.mutate({ is_active: !user.is_active })}
            >
              {user.is_active ? "Deactivate" : "Reactivate"}
            </button>
            <button
              type="button"
              className="btn btn-small"
              onClick={() => {
                setSaved(false);
                setResetting(true);
              }}
            >
              Reset password
            </button>
          </div>
          {saved && (
            <span className="muted small" role="status">
              Password changed.
            </span>
          )}
          <InlineError error={patch.error} />
        </td>
      </tr>
      {resetting && (
        <tr>
          <td colSpan={6}>
            <PasswordReset
              user={user}
              onDone={() => {
                setResetting(false);
                setSaved(true);
              }}
            />
          </td>
        </tr>
      )}
    </>
  );
}

export function UsersPage() {
  const me = useUser();
  const { page, update } = useSearchState();
  const [creating, setCreating] = useState(false);
  const users = useQuery({
    queryKey: ["users", page],
    queryFn: () => api<Page<User>>("/users", { query: { page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="page">
      <header className="page-head row">
        <div>
          <h1>Users</h1>
          <p className="muted">Admins create accounts, change roles and deactivate people. Every change is recorded in the audit log.</p>
        </div>
        {!creating && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            New user
          </button>
        )}
      </header>

      {creating && <NewUserForm onDone={() => setCreating(false)} />}

      {users.isPending ? (
        <Loading />
      ) : users.isError ? (
        <ErrorState error={users.error} onRetry={() => users.refetch()} />
      ) : users.data.items.length === 0 ? (
        <Empty title="No users" />
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last sign-in</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((u) => (
                  <UserRow key={u.id} user={u} isSelf={u.id === me.id} />
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={users.data.total} onPage={(p) => update({ page: String(p) }, true)} />
        </>
      )}
    </div>
  );
}
