import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { branchIds, type Role } from "./roles";

interface BranchState {
  /** Branches the current section lets the user work in: managed branches under /branch, else managed or till branches. */
  branches: string[];
  /** The branch the user is working in: always one of `branches`, or null if they work at none. */
  branchId: string | null;
  selectBranch: (branchId: string) => void;
}

const STORAGE_KEY = "retail.branch";
const MANAGER: Role[] = ["BRANCH_MANAGER"];
const STAFF: Role[] = ["BRANCH_MANAGER", "CASHIER"];
const BranchContext = createContext<BranchState | null>(null);

function loadChoice(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function BranchProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const roles = /^\/branch(\/|$)/.test(useLocation().pathname) ? MANAGER : STAFF;
  const [choice, setChoice] = useState(loadChoice);

  const selectBranch = useCallback((branchId: string) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, branchId);
    } catch {
      /* storage unavailable: choice lasts until reload */
    }
    setChoice(branchId);
  }, []);

  const value = useMemo<BranchState>(() => {
    const branches = branchIds(user, roles) ?? [];
    const branchId = choice !== null && branches.includes(choice) ? choice : (branches[0] ?? null);
    return { branches, branchId, selectBranch };
  }, [user, roles, choice, selectBranch]);

  return <BranchContext.Provider value={value}>{children}</BranchContext.Provider>;
}

export function useBranch(): BranchState {
  const ctx = useContext(BranchContext);
  if (!ctx) throw new Error("useBranch must be used inside <BranchProvider>");
  return ctx;
}
