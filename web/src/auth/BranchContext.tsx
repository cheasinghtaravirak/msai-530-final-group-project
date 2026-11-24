import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { useAuth } from "./AuthContext";
import { branchIds } from "./roles";

interface BranchState {
  /** Branches the user manages, from the token. */
  branches: string[];
  /** The branch the user is working in: always one of `branches`, or null if they manage none. */
  branchId: string | null;
  selectBranch: (branchId: string) => void;
}

const STORAGE_KEY = "retail.branch";
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
    const branches = branchIds(user, ["BRANCH_MANAGER"]) ?? [];
    const branchId = choice !== null && branches.includes(choice) ? choice : (branches[0] ?? null);
    return { branches, branchId, selectBranch };
  }, [user, choice, selectBranch]);

  return <BranchContext.Provider value={value}>{children}</BranchContext.Provider>;
}

export function useBranch(): BranchState {
  const ctx = useContext(BranchContext);
  if (!ctx) throw new Error("useBranch must be used inside <BranchProvider>");
  return ctx;
}
