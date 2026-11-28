import { Card, Grid, Skeleton, Stack } from "@mantine/core";
import { IconChartLine, IconFileText } from "@tabler/icons-react";

import { EmptyState, PageHeader, StatTile } from "../../ui";
import { useBranches } from "./BranchesPage";

export function HqDashboard() {
  const branches = useBranches();
  const total = branches.data?.length;
  const open = branches.data?.filter((b) => b.status === "OPEN").length;

  return (
    <Stack gap="xl">
      <PageHeader title="Company dashboard" description="How every branch is doing, in one place." />
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 4 }}>
          <StatTile
            label="Open branches"
            value={branches.isLoading ? <Skeleton height={36} width={64} radius="sm" /> : (open ?? "-")}
            hint={
              branches.isError
                ? "Couldn't load branches"
                : total !== undefined
                  ? `of ${total} branch${total === 1 ? "" : "es"}`
                  : " "
            }
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card h="100%">
            <EmptyState icon={IconChartLine} title="Sales reports">
              Sales by branch and day, with a branch comparison, appear here once stores start selling. Arrives in Phase
              4.
            </EmptyState>
          </Card>
        </Grid.Col>
        <Grid.Col span={12}>
          <Card>
            <EmptyState icon={IconFileText} title="Morning briefing">
              A short written summary of the company's numbers, prepared each night. Arrives in Phase 4.
            </EmptyState>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
