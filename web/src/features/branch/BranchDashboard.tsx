import { Stack, Text, Title } from "@mantine/core";

import { useAuth } from "../../auth/AuthContext";
import { branchIds } from "../../auth/roles";

export function BranchDashboard() {
  const { user } = useAuth();
  const ids = branchIds(user, ["HQ_ADMIN", "BRANCH_MANAGER"]);

  return (
    <Stack>
      <Title order={2}>Branch dashboard</Title>
      <Text c="dimmed">
        {ids === null ? "All branches" : ids.join(", ")}: today so far, stock, forecasts and reorder suggestions arrive in
        Phases 3–4.
      </Text>
    </Stack>
  );
}
