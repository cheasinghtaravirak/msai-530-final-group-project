import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { hasRole, type Role } from "./roles";

/** Renders children only for a logged-in user holding one of `roles` (any role if omitted). */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !hasRole(user, roles)) return <Navigate to="/no-access" replace />;
  return <>{children}</>;
}
