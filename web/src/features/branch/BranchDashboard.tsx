import { Stack, Text, Title } from "@mantine/core";

import { useBranch } from "../../auth/BranchContext";

export function BranchDashboard() {
  const { branchId } = useBranch();

  return (
    <Stack>
      <Title order={2}>Branch dashboard</Title>
      <Text c="dimmed">
        {branchId ?? "All branches"}: today so far, stock, forecasts and reorder suggestions arrive in Phases 3–4.
      </Text>
    </Stack>
  );
}
