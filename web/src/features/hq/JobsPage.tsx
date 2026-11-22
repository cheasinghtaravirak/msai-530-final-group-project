import { Alert, Badge, Button, Code, Group, Stack, Table, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";

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
  RUNNING: "blue",
  DONE: "teal",
  FAILED: "red",
};

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
    <Stack>
      <Title order={2}>Jobs</Title>
      <Text c="dimmed" size="sm">
        Nightly jobs run automatically at 00:30. Use these buttons to run them now (for example before a demo).
      </Text>
      {runs.error && <Alert color="red">{(runs.error as Error).message}</Alert>}
      <Group gap="xs">
        {runs.data?.jobs.map((job) => (
          <Button
            key={job}
            variant={job === "nightly" ? "filled" : "light"}
            size="xs"
            onClick={() => runNow.mutate(job)}
            loading={runNow.isPending && runNow.variables === job}
          >
            Run {job}
          </Button>
        ))}
      </Group>
      <Table.ScrollContainer minWidth={640}>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Job</Table.Th>
              <Table.Th>Trigger</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Started</Table.Th>
              <Table.Th>Message</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {runs.data?.results.map((r) => (
              <Table.Tr key={r.run_id}>
                <Table.Td>{r.job}</Table.Td>
                <Table.Td>{r.trigger}</Table.Td>
                <Table.Td>
                  <Badge color={STATUS_COLOR[r.status]} variant="light">
                    {r.status}
                  </Badge>
                </Table.Td>
                <Table.Td>{r.started_at ? new Date(r.started_at).toLocaleString() : "—"}</Table.Td>
                <Table.Td>
                  <Code block style={{ whiteSpace: "pre-wrap" }}>
                    {r.message || "—"}
                  </Code>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}
