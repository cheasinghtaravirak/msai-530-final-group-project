import { Badge, Button, Card, Group, Skeleton, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconClockPlay, IconPlayerPlay } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { EmptyState, ErrorState, humanize, PageHeader, TableSkeleton } from "../../ui";

interface JobRun {
  run_id: string;
  job: string;
  trigger: "SCHEDULE" | "MANUAL";
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED";
  message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

const STATUS_COLOR: Record<JobRun["status"], string> = {
  QUEUED: "gray",
  RUNNING: "accent",
  DONE: "green",
  FAILED: "red",
};
const COLUMNS = ["Job", "Trigger", "Status", "Started", "Message"];
const DATE_FORMAT: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "medium" };

export function JobsPage() {
  const queryClient = useQueryClient();
  const runs = useQuery({
    queryKey: ["job-runs"],
    queryFn: () => api<{ results: JobRun[]; jobs: string[] }>("/analytics/jobs/runs?limit=30"),
    refetchInterval: 3000,
  });
  const runNow = useMutation({
    mutationFn: (job: string) => api<JobRun>(`/analytics/jobs/${job}/run`, { method: "POST" }),
    onSuccess: (run) => {
      notifications.show({ message: `Queued ${run.job}` });
      queryClient.invalidateQueries({ queryKey: ["job-runs"] });
    },
    onError: (e) => notifications.show({ color: "red", message: (e as Error).message }),
  });

  return (
    <Stack gap="xl">
      <Stack gap="lg">
        <PageHeader
          title="Scheduled jobs"
          description="Nightly jobs run automatically at 00:30. Run one now when you need fresh numbers, for example before a demo."
        />
        <Group gap="xs">
          {runs.isLoading ? (
            <Skeleton height={36} width={320} radius="md" />
          ) : (
            [...(runs.data?.jobs ?? [])]
              .sort((a, b) => Number(b === "nightly") - Number(a === "nightly"))
              .map((job) => (
                <Button
                  key={job}
                  variant={job === "nightly" ? "filled" : "default"}
                  leftSection={<IconPlayerPlay size={14} stroke={2} />}
                  onClick={() => runNow.mutate(job)}
                  loading={runNow.isPending && runNow.variables === job}
                >
                  Run {job}
                </Button>
              ))
          )}
        </Group>
      </Stack>
      {runs.error && <ErrorState error={runs.error} onRetry={() => runs.refetch()} />}
      {runs.data?.results.length === 0 ? (
        <Card>
          <EmptyState icon={IconClockPlay} title="No runs yet">
            Runs appear here after the nightly schedule fires or when you run a job now.
          </EmptyState>
        </Card>
      ) : (
        (runs.isLoading || runs.data) && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={720} type="native">
              <Table highlightOnHover className="table-top">
                <Table.Thead className="table-head">
                  <Table.Tr>
                    {COLUMNS.map((c) => (
                      <Table.Th key={c}>{c}</Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                {runs.isLoading ? (
                  <TableSkeleton columns={COLUMNS.length} />
                ) : (
                  <Table.Tbody>
                    {runs.data?.results.map((r) => (
                      <Table.Tr key={r.run_id}>
                        <Table.Td fw={600}>{r.job}</Table.Td>
                        <Table.Td>{humanize(r.trigger)}</Table.Td>
                        <Table.Td>
                          <Badge color={STATUS_COLOR[r.status]}>{humanize(r.status)}</Badge>
                        </Table.Td>
                        <Table.Td>
                          {r.started_at ? (
                            new Date(r.started_at).toLocaleString(undefined, DATE_FORMAT)
                          ) : (
                            <Text span c="dimmed" inherit>
                              Not started
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td>{r.message && <div className="job-message">{r.message}</div>}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                )}
              </Table>
            </Table.ScrollContainer>
          </Card>
        )
      )}
    </Stack>
  );
}
