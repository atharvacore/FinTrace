import { NavLink, Outlet } from "react-router";
import { useAuth, useUser } from "../auth/AuthContext";
import { humanize } from "../lib/format";
import { hasRole } from "../lib/roles";

export function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  const links = [
    { to: "/", label: "Overview", end: true },
    { to: "/alerts", label: "Alert queue" },
    { to: "/cases", label: "Cases" },
    { to: "/transactions", label: "Transactions" },
    { to: "/model", label: "Model evaluation" },
    { to: "/rules", label: "Rules" },
    ...(hasRole(user, "senior_analyst") ? [{ to: "/audit", label: "Audit log" }] : []),
  ];
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          FinTrace
        </div>
        <nav aria-label="Main">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className="nav-link">
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user">
          <div>{user.full_name}</div>
          <div className="muted small">{humanize(user.role)}</div>
          <button type="button" className="btn btn-small btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <div className="banner" role="note">
          Portfolio prototype on <strong>synthetic data</strong>. Risk scores are triage signals for human
          review, not proof of wrongdoing. Not validated for real anti-money-laundering decisions.
        </div>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
