import { Alert, Badge, Button, Card, Group, Modal, Select, Stack, Table, Text, TextInput } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconMapPins, IconPlus } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "../../api/client";
import { EmptyState, ErrorState, humanize, PageHeader, TableSkeleton } from "../../ui";

export interface Branch {
  branch_id: string;
  name: string;
  address: string;
  region: string;
  timezone: string;
  status: "OPEN" | "CLOSED";
  opened_on: string | null;
}

const REGIONS = ["PHNOM_PENH", "SIEM_REAP", "BATTAMBANG", "SIHANOUKVILLE", "KAMPOT"];
const REGION_OPTIONS = REGIONS.map((r) => ({ value: r, label: humanize(r) }));
const COLUMNS = ["ID", "Name", "Region", "Address", "Status", ""];

export function useBranches() {
  return useQuery({
    queryKey: ["branches"],
    queryFn: () => api<{ results: Branch[] }>("/admin/branches").then((r) => r.results),
  });
}

export function BranchesPage() {
  const { data, isLoading, error, refetch } = useBranches();
  const [opened, { open, close }] = useDisclosure(false);
  const [closing, setClosing] = useState<Branch | null>(null);

  return (
    <Stack gap="xl">
      <PageHeader
        title="Branches"
        description="Every store in the company and whether it is trading."
        actions={
          <Button leftSection={<IconPlus size={16} stroke={2} />} onClick={open}>
            New branch
          </Button>
        }
      />
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {data?.length === 0 ? (
        <Card>
          <EmptyState icon={IconMapPins} title="No branches yet">
            Branches you create with New branch appear here.
          </EmptyState>
        </Card>
      ) : (
        (isLoading || data) && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={560} type="native">
              <Table highlightOnHover>
                <Table.Thead className="table-head">
                  <Table.Tr>
                    {COLUMNS.map((c) => (
                      <Table.Th key={c}>{c}</Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                {isLoading ? (
                  <TableSkeleton columns={COLUMNS.length} />
                ) : (
                  <Table.Tbody>
                    {data?.map((b) => (
                      <Table.Tr key={b.branch_id}>
                        <Table.Td fw={600}>{b.branch_id}</Table.Td>
                        <Table.Td>{b.name}</Table.Td>
                        <Table.Td>{humanize(b.region)}</Table.Td>
                        <Table.Td c="dimmed">{b.address}</Table.Td>
                        <Table.Td>
                          <Badge color={b.status === "OPEN" ? "green" : "gray"}>{humanize(b.status)}</Badge>
                        </Table.Td>
                        <Table.Td ta="right">
                          {b.status === "OPEN" && (
                            <Button
                              size="xs"
                              variant="subtle"
                              color="red"
                              aria-label={`Close ${b.branch_id}`}
                              onClick={() => setClosing(b)}
                            >
                              Close
                            </Button>
                          )}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                )}
              </Table>
            </Table.ScrollContainer>
          </Card>
        )
      )}
      <Modal opened={opened} onClose={close} title={<Text fw={600}>New branch</Text>}>
        <NewBranchForm onDone={close} />
      </Modal>
      <Modal opened={closing !== null} onClose={() => setClosing(null)} title={<Text fw={600}>Close branch</Text>}>
        {closing && <CloseBranchConfirm branch={closing} onDone={() => setClosing(null)} />}
      </Modal>
    </Stack>
  );
}

function NewBranchForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ branch_id: "", name: "", region: REGIONS[0], address: "" });
  const create = useMutation({
    mutationFn: () => api<Branch>("/admin/branches", { method: "POST", json: form }),
    onSuccess: (b) => {
      notifications.show({ color: "green", message: `Branch ${b.branch_id} created` });
      queryClient.invalidateQueries({ queryKey: ["branches"] });
      onDone();
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  const err = create.error instanceof ApiError ? create.error : null;
  return (
    <form onSubmit={onSubmit}>
      <Stack>
        {err && <Alert color="red">{err.message}</Alert>}
        <TextInput
          label="Branch ID"
          placeholder="BR-06"
          required
          value={form.branch_id}
          onChange={(e) => setForm({ ...form, branch_id: e.currentTarget.value.toUpperCase() })}
        />
        <TextInput
          label="Name"
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
        />
        <Select
          label="Region"
          data={REGION_OPTIONS}
          value={form.region}
          allowDeselect={false}
          onChange={(v) => setForm({ ...form, region: v ?? REGIONS[0] })}
        />
        <TextInput
          label="Address"
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.currentTarget.value })}
        />
        <Button type="submit" loading={create.isPending} mt="xs">
          Create branch
        </Button>
      </Stack>
    </form>
  );
}

function CloseBranchConfirm({ branch, onDone }: { branch: Branch; onDone: () => void }) {
  const queryClient = useQueryClient();
  const closeBranch = useMutation({
    mutationFn: () => api<Branch>(`/admin/branches/${branch.branch_id}/close`, { method: "POST" }),
    onSuccess: (b) => {
      notifications.show({ color: "green", message: `Branch ${b.branch_id} closed` });
      queryClient.invalidateQueries({ queryKey: ["branches"] });
      onDone();
    },
  });

  return (
    <Stack>
      {closeBranch.error && <Alert color="red">{closeBranch.error.message}</Alert>}
      <Text>
        Close {branch.branch_id} {branch.name}? Its managers and cashiers lose their roles here. Anyone already signed
        in can keep working here until their sign-in runs out, up to 8 hours later.
      </Text>
      <Group justify="flex-end" gap="xs">
        <Button variant="default" onClick={onDone}>
          Cancel
        </Button>
        <Button color="red" loading={closeBranch.isPending} onClick={() => closeBranch.mutate()}>
          Close branch
        </Button>
      </Group>
    </Stack>
  );
}
