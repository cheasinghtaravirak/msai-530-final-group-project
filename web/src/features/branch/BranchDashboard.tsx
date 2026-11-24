import { Card, Grid, Stack } from "@mantine/core";
import { IconChartLine, IconPackage, IconTrendingUp } from "@tabler/icons-react";

import { useBranch } from "../../auth/BranchContext";
import { EmptyState, PageHeader } from "../../ui";

export function BranchDashboard() {
  const { branchId } = useBranch();

  return (
    <Stack gap="xl">
      <PageHeader title="Branch dashboard" description={branchId ? `Showing ${branchId}.` : "Showing all branches."} />
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card h="100%">
            <EmptyState icon={IconChartLine} title="Today so far">
              Sales, orders and this month against last, updated through the day. Arrives in Phase 4.
            </EmptyState>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card h="100%">
            <EmptyState icon={IconPackage} title="Stock">
              What's on hand and what's running low. Arrives in Phase 3.
            </EmptyState>
          </Card>
        </Grid.Col>
        <Grid.Col span={12}>
          <Card>
            <EmptyState icon={IconTrendingUp} title="Forecasts and reorder suggestions">
              Expected demand per product and suggested orders to approve. Arrives in Phase 4.
            </EmptyState>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
