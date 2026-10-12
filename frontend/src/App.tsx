import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Empty, Loading } from "./components/States";
import { hasRole } from "./lib/roles";
import { AlertDetailPage } from "./pages/AlertDetailPage";
import { AlertsPage } from "./pages/AlertsPage";
import { AuditPage } from "./pages/AuditPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CasesPage } from "./pages/CasesPage";
import { LoginPage } from "./pages/LoginPage";
import { ModelPage } from "./pages/ModelPage";
import { OverviewPage } from "./pages/OverviewPage";
import { RulesPage } from "./pages/RulesPage";
import { TransactionDetailPage } from "./pages/TransactionDetailPage";
import { TransactionsPage } from "./pages/TransactionsPage";

function RequireLogin() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <Outlet />;
}

function SeniorOnly() {
  const { user } = useAuth();
  return hasRole(user, "senior_analyst") ? <Outlet /> : <Empty title="Senior analysts only" />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireLogin />}>
        <Route element={<Layout />}>
          <Route index element={<OverviewPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="alerts/:alertId" element={<AlertDetailPage />} />
          <Route path="cases" element={<CasesPage />} />
          <Route path="cases/:caseId" element={<CaseDetailPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/:transactionId" element={<TransactionDetailPage />} />
          <Route path="model" element={<ModelPage />} />
          <Route path="rules" element={<RulesPage />} />
          <Route element={<SeniorOnly />}>
            <Route path="audit" element={<AuditPage />} />
          </Route>
          <Route path="*" element={<Empty title="Page not found" />} />
        </Route>
      </Route>
    </Routes>
  );
}
