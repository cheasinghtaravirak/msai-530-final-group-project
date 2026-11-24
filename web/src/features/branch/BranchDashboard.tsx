import { Anchor, Card, Grid, Group, SimpleGrid, Skeleton, Stack, Text, Title } from "@mantine/core";
import { IconBuildingStore, IconTrendingUp } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import type { Page, SalesPeriod, StockRow } from "../../api/types";
import { useBranch } from "../../auth/BranchContext";
import { EmptyState, ErrorState, formatMoney, PageHeader, StatTile } from "../../ui";

const loading = <Skeleton height={36} width={96} radius="sm" />;

export function BranchDashboard() {
  const { branchId } = useBranch();

  if (!branchId) {
    return (
      <Stack gap="xl">
        <PageHeader title="Branch dashboard" />
        <Card>
          <EmptyState icon={IconBuildingStore} title="No branch to show">
            This dashboard shows a branch you manage, and your account manages none. Company-wide numbers live on the
            company dashboard.
          </EmptyState>
        </Card>
      </Stack>
    );
  }

  return (
    <Stack gap="xl">
      <PageHeader title="Branch dashboard" description={`Showing ${branchId}.`} />
      <TodaySoFar branchId={branchId} />
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <StockAlerts branchId={branchId} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card h="100%">
            <EmptyState icon={IconTrendingUp} title="Forecasts and reorder suggestions">
              Expected demand per product and suggested orders to approve. Arrives in Phase 4.
            </EmptyState>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

function TodaySoFar({ branchId }: { branchId: string }) {
  const report = useQuery({
    queryKey: ["sales-report", branchId],
    queryFn: () => {
      const params = new URLSearchParams({ scope: "branch", branch_id: branchId, grain: "day" });
      return api<Page<SalesPeriod>>(`/analytics/reports/sales?${params}`);
    },
    refetchInterval: 3000,
  });
  const day = report.data?.results[0];
  const show = (value: (d: SalesPeriod) => ReactNode) => (day ? value(day) : report.isLoading ? loading : "-");

  return (
    <Stack gap="sm">
      <Title order={2}>Today so far</Title>
      {report.error && <ErrorState error={report.error} onRetry={() => report.refetch()} />}
      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="lg">
        <StatTile label="Revenue" value={show((d) => formatMoney(d.revenue))} hint="Net of refunds" />
        <StatTile label="Orders" value={show((d) => d.orders)} />
        <StatTile label="Units sold" value={show((d) => d.units)} />
        <StatTile label="Average basket" value={show((d) => formatMoney(d.avg_basket))} />
      </SimpleGrid>
    </Stack>
  );
}

function useStockCount(branchId: string, flag: "low_only" | "negative_only") {
  return useQuery({
    queryKey: ["stock-count", branchId, flag],
    queryFn: () => {
      const params = new URLSearchParams({ branch_id: branchId, [flag]: "true", page_size: "1" });
      return api<Page<StockRow>>(`/inventory/stock?${params}`).then((r) => r.count);
    },
    refetchInterval: 5000,
  });
}

function StockAlerts({ branchId }: { branchId: string }) {
  const low = useStockCount(branchId, "low_only");
  const negative = useStockCount(branchId, "negative_only");
  const rows = [
    { label: "Running low", query: low, filter: "low", color: "orange.7" },
    { label: "Below zero", query: negative, filter: "negative", color: "red.7" },
  ];

  return (
    <Card h="100%">
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={3}>Stock</Title>
          <Anchor component={Link} to="/branch/stock" size="sm">
            View all stock
          </Anchor>
        </Group>
        {low.error && <ErrorState error={low.error} onRetry={() => low.refetch()} />}
        <SimpleGrid cols={2}>
          {rows.map(({ label, query, filter, color }) => (
            <Anchor
              key={filter}
              component={Link}
              to={`/branch/stock?filter=${filter}`}
              underline="never"
              c="inherit"
              aria-label={`${label}: ${query.data ?? "loading"} products. Show them.`}
            >
              <Text size="sm" fw={500} c="dimmed">
                {label}
              </Text>
              <Text component="div" className="stat-value" mt={6} c={query.data ? color : undefined}>
                {query.data ?? (query.isLoading ? loading : "-")}
              </Text>
              <Text size="sm" c="dimmed" mt={4}>
                products
              </Text>
            </Anchor>
          ))}
        </SimpleGrid>
      </Stack>
    </Card>
  );
}
