export type Role = "HQ_ADMIN" | "BRANCH_MANAGER" | "CASHIER" | "CUSTOMER";

export interface RoleGrant {
  role: Role;
  branch_id: string | null;
}

export interface CurrentUser {
  user_id: string;
  full_name: string;
  email: string;
  roles: RoleGrant[];
}

export function hasRole(user: CurrentUser | null, roles: Role[], branchId?: string): boolean {
  if (!user) return false;
  return user.roles.some(
    (g) => roles.includes(g.role) && (branchId === undefined || g.branch_id === null || g.branch_id === branchId),
  );
}

/** Branches the user can act on with these roles; null means all branches. */
export function branchIds(user: CurrentUser | null, roles: Role[]): string[] | null {
  if (!user) return [];
  const ids = new Set<string>();
  for (const g of user.roles) {
    if (!roles.includes(g.role)) continue;
    if (g.branch_id === null) return null;
    ids.add(g.branch_id);
  }
  return [...ids].sort();
}

/** Where a user lands after login. */
export function homePath(user: CurrentUser): string {
  if (hasRole(user, ["HQ_ADMIN"])) return "/hq";
  if (hasRole(user, ["BRANCH_MANAGER"])) return "/branch";
  if (hasRole(user, ["CASHIER"])) return "/pos";
  return "/no-access";
}
