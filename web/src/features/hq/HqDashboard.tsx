import { Card, SimpleGrid, Stack, Text, Title } from "@mantine/core";

import { useBranches } from "./BranchesPage";

export function HqDashboard() {
  const branches = useBranches();
  const open = branches.data?.filter((b) => b.status === "OPEN").length;

  return (
    <Stack>
      <Title order={2}>Company dashboard</Title>
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Card withBorder>
          <Text size="sm" c="dimmed">
            Open branches
          </Text>
          <Text fz={32} fw={700}>
            {open ?? "—"}
          </Text>
        </Card>
        <Card withBorder>
          <Text size="sm" c="dimmed">
            AI briefing
          </Text>
          <Text>Arrives in Phase 4 (J7).</Text>
        </Card>
        <Card withBorder>
          <Text size="sm" c="dimmed">
            Sales reports
          </Text>
          <Text>Arrive in Phase 3–4.</Text>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}
