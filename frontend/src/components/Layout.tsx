import { NavLink, Outlet } from "react-router";
import { useAuth, useUser } from "../auth/AuthContext";
import { humanize } from "../lib/format";
import { hasRole } from "../lib/roles";
import { BrandMark } from "./BrandMark";
import { ThemeToggle } from "./ThemeToggle";

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "")).toUpperCase() || "?";
}

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
          <BrandMark />
          <span className="brand-name">FinTrace</span>
          <span className="brand-sub">Investigation desk</span>
        </div>
        <nav aria-label="Main">
          {links.map((link, i) => (
            <NavLink key={link.to} to={link.to} end={link.end} className="nav-link">
              <span className="nav-num" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user">
          <span className="avatar" aria-hidden="true">
            {initials(user.full_name)}
          </span>
          <div>{user.full_name}</div>
          <div className="muted small">{humanize(user.role)}</div>
          <ThemeToggle />
          <button type="button" className="btn btn-small btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <div className="banner" role="note">
          <span className="stamp">Synthetic data</span>
          <span>
            Portfolio prototype on <strong>synthetic data</strong>. Risk scores are triage signals for human review,
            not proof of wrongdoing. Not validated for real anti-money-laundering decisions.
          </span>
        </div>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
