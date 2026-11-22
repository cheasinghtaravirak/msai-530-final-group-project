import { Alert, Badge, Button, Group, Modal, Select, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "../../api/client";

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

export function useBranches() {
  return useQuery({
    queryKey: ["branches"],
    queryFn: () => api<{ results: Branch[] }>("/admin/branches").then((r) => r.results),
  });
}

export function BranchesPage() {
  const { data, isLoading, error } = useBranches();
  const [opened, { open, close }] = useDisclosure(false);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Branches</Title>
        <Button onClick={open}>New branch</Button>
      </Group>
      {error && <Alert color="red">{(error as Error).message}</Alert>}
      {isLoading ? (
        <Text c="dimmed">Loading…</Text>
      ) : (
        <Table.ScrollContainer minWidth={560}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Name</Table.Th>
                <Table.Th>Region</Table.Th>
                <Table.Th>Address</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((b) => (
                <Table.Tr key={b.branch_id}>
                  <Table.Td>{b.branch_id}</Table.Td>
                  <Table.Td>{b.name}</Table.Td>
                  <Table.Td>{b.region}</Table.Td>
                  <Table.Td>{b.address}</Table.Td>
                  <Table.Td>
                    <Badge color={b.status === "OPEN" ? "teal" : "gray"} variant="light">
                      {b.status}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
              {data?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text c="dimmed" size="sm">
                      No branches yet.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Modal opened={opened} onClose={close} title="New branch">
        <NewBranchForm onDone={close} />
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
      notifications.show({ color: "teal", message: `Branch ${b.branch_id} created` });
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
        <TextInput label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} />
        <Select label="Region" data={REGIONS} value={form.region} onChange={(v) => setForm({ ...form, region: v ?? REGIONS[0] })} />
        <TextInput label="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.currentTarget.value })} />
        <Button type="submit" loading={create.isPending}>
          Create
        </Button>
      </Stack>
    </form>
  );
}
