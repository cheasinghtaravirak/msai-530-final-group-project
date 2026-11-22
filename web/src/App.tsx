import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { RequireRole } from "./auth/RequireRole";
import { homePath } from "./auth/roles";
import { BranchDashboard } from "./features/branch/BranchDashboard";
import { BranchesPage } from "./features/hq/BranchesPage";
import { HqDashboard } from "./features/hq/HqDashboard";
import { JobsPage } from "./features/hq/JobsPage";
import { PosPage } from "./features/pos/PosPage";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { MessagePage } from "./pages/MessagePage";

function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homePath(user) : "/login"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireRole>
            <AppLayout />
          </RequireRole>
        }
      >
        <Route index element={<HomeRedirect />} />
        <Route path="hq" element={<RequireRole roles={["HQ_ADMIN"]}><HqDashboard /></RequireRole>} />
        <Route path="hq/branches" element={<RequireRole roles={["HQ_ADMIN"]}><BranchesPage /></RequireRole>} />
        <Route path="hq/jobs" element={<RequireRole roles={["HQ_ADMIN"]}><JobsPage /></RequireRole>} />
        <Route
          path="branch"
          element={<RequireRole roles={["HQ_ADMIN", "BRANCH_MANAGER"]}><BranchDashboard /></RequireRole>}
        />
        <Route path="pos" element={<RequireRole roles={["BRANCH_MANAGER", "CASHIER"]}><PosPage /></RequireRole>} />
        <Route path="no-access" element={<MessagePage title="No access" text="Your account has no role for this page." />} />
        <Route path="*" element={<MessagePage title="Page not found" text="This page does not exist." />} />
      </Route>
    </Routes>
  );
}
