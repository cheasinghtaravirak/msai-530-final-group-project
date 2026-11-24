import {
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  Modal,
  NumberInput,
  Pagination,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconBuildingStore, IconPackage, IconSearch } from "@tabler/icons-react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import type { Movement, Page, StockRow } from "../../api/types";
import { useBranch } from "../../auth/BranchContext";
import { EmptyState, ErrorState, formatDateTime, humanize, PageHeader, TableSkeleton } from "../../ui";

const PAGE_SIZE = 50;
const COLUMNS = ["SKU", "Name", "On hand", "On order", "Status", ""];
const FILTERS = [
  { value: "all", label: "All" },
  { value: "low", label: "Low" },
  { value: "negative", label: "Negative" },
];
const FILTER_PARAM: Record<string, Record<string, string>> = {
  all: {},
  low: { low_only: "true" },
  negative: { negative_only: "true" },
};
// Sales land through Kafka, so the page polls to show them within a few seconds.
const REFRESH_MS = 5000;

function StockBadge({ row }: { row: StockRow }) {
  if (row.on_hand < 0) return <Badge color="red">Negative</Badge>;
  if (row.low) return <Badge color="yellow">Low</Badge>;
  return null;
}

export function StockPage() {
  const { branchId } = useBranch();
  if (!branchId) {
    return (
      <Stack gap="xl">
        <PageHeader title="Stock" />
        <Card>
          <EmptyState icon={IconBuildingStore} title="No branch to show">
            Stock is for branch managers. Your account manages no branch.
          </EmptyState>
        </Card>
      </Stack>
    );
  }
  return <BranchStock key={branchId} branchId={branchId} />;
}

function BranchStock({ branchId }: { branchId: string }) {
  const [params, setParams] = useSearchParams();
  const filter = params.get("filter") === "low" || params.get("filter") === "negative" ? params.get("filter")! : "all";
  const [search, setSearch] = useState("");
  const [q] = useDebouncedValue(search.trim(), 300);
  const [page, setPage] = useState(1);
  const [historySku, setHistorySku] = useState<string | null>(null);
  const [adjusting, setAdjusting] = useState<StockRow | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["stock", branchId, { q, filter, page }],
    queryFn: () => {
      const query = new URLSearchParams({
        branch_id: branchId,
        page: String(page),
        page_size: String(PAGE_SIZE),
        ...FILTER_PARAM[filter],
      });
      if (q) query.set("q", q);
      return api<Page<StockRow>>(`/inventory/stock?${query}`);
    },
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  });
  const pages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);
  const historyRow = data?.results.find((r) => r.sku === historySku) ?? null;

  return (
    <Stack gap="xl">
      <PageHeader title="Stock" description={`What ${branchId} has on hand, updated every few seconds.`} />
      <Group gap="sm" align="flex-end">
        <TextInput
          aria-label="Search stock"
          placeholder="SKU or name"
          leftSection={<IconSearch size={16} stroke={1.6} />}
          w={280}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value);
            setPage(1);
          }}
        />
        <SegmentedControl
          aria-label="Show"
          data={FILTERS}
          value={filter}
          onChange={(v) => {
            setParams(v === "all" ? {} : { filter: v }, { replace: true });
            setPage(1);
          }}
        />
      </Group>
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {data?.count === 0 ? (
        <Card>
          <EmptyState icon={IconPackage} title="No stock rows">
            {q || filter !== "all" ? "Nothing matches this search or filter." : "Stock appears once goods arrive."}
          </EmptyState>
        </Card>
      ) : (
        (isLoading || data) && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={640} type="native">
              <Table highlightOnHover>
                <Table.Thead className="table-head">
                  <Table.Tr>
                    {COLUMNS.map((c) => (
                      <Table.Th key={c} ta={c === "On hand" || c === "On order" ? "right" : undefined}>
                        {c}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                {isLoading ? (
                  <TableSkeleton columns={COLUMNS.length} />
                ) : (
                  <Table.Tbody>
                    {data?.results.map((r) => (
                      <Table.Tr key={r.sku} style={{ cursor: "pointer" }} onClick={() => setHistorySku(r.sku)}>
                        <Table.Td fw={600}>{r.sku}</Table.Td>
                        <Table.Td c={r.name ? undefined : "dimmed"}>{r.name || "Unknown product"}</Table.Td>
                        <Table.Td className="num" ta="right" fw={600} c={r.on_hand < 0 ? "red" : undefined}>
                          {r.on_hand}
                        </Table.Td>
                        <Table.Td className="num" ta="right" c="dimmed">
                          {r.on_order}
                        </Table.Td>
                        <Table.Td>
                          <StockBadge row={r} />
                        </Table.Td>
                        <Table.Td ta="right">
                          <Group gap={4} justify="flex-end" wrap="nowrap">
                            <Button
                              size="xs"
                              variant="subtle"
                              color="gray"
                              aria-label={`Movement history for ${r.sku}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                setHistorySku(r.sku);
                              }}
                            >
                              History
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              aria-label={`Adjust stock for ${r.sku}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                setAdjusting(r);
                              }}
                            >
                              Adjust
                            </Button>
                          </Group>
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
      {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
      <Drawer
        opened={historySku !== null}
        onClose={() => setHistorySku(null)}
        position="right"
        size="lg"
        title={<Text fw={600}>Movements for {historySku}</Text>}
      >
        {historySku && (
          <MovementHistory
            branchId={branchId}
            sku={historySku}
            row={historyRow}
            onAdjust={() => historyRow && setAdjusting(historyRow)}
          />
        )}
      </Drawer>
      <Modal
        opened={adjusting !== null}
        onClose={() => setAdjusting(null)}
        title={<Text fw={600}>Adjust {adjusting?.sku}</Text>}
      >
        {adjusting && <AdjustForm branchId={branchId} row={adjusting} onDone={() => setAdjusting(null)} />}
      </Modal>
    </Stack>
  );
}

function MovementHistory({
  branchId,
  sku,
  row,
  onAdjust,
}: {
  branchId: string;
  sku: string;
  row: StockRow | null;
  onAdjust: () => void;
}) {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["movements", branchId, sku, page],
    queryFn: () =>
      api<Page<Movement>>(
        `/inventory/stock/${encodeURIComponent(branchId)}/${encodeURIComponent(sku)}/movements?page=${page}&page_size=${PAGE_SIZE}`,
      ),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  });
  const pages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  return (
    <Stack gap="lg">
      {row && (
        <Group justify="space-between">
          <div>
            <Text size="sm" c="dimmed">
              {row.name || "Unknown product"}
            </Text>
            <Group gap="xs">
              <Text className="stat-value">{row.on_hand}</Text>
              <StockBadge row={row} />
            </Group>
            <Text size="sm" c="dimmed">
              on hand, {row.on_order} on order
            </Text>
          </div>
          <Button variant="light" onClick={onAdjust}>
            Adjust stock
          </Button>
        </Group>
      )}
      {error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data?.count === 0 ? (
        <Text c="dimmed">No movements yet.</Text>
      ) : (
        <Table>
          <Table.Thead className="table-head">
            <Table.Tr>
              <Table.Th>When</Table.Th>
              <Table.Th>Reason</Table.Th>
              <Table.Th ta="right">Change</Table.Th>
              <Table.Th>Reference</Table.Th>
            </Table.Tr>
          </Table.Thead>
          {isLoading ? (
            <TableSkeleton columns={4} rows={3} />
          ) : (
            <Table.Tbody>
              {data?.results.map((m) => (
                <Table.Tr key={m.movement_id}>
                  <Table.Td className="num">{formatDateTime(m.occurred_at)}</Table.Td>
                  <Table.Td>
                    <Badge color={m.reason === "ADJUST" ? "yellow" : "gray"}>{humanize(m.reason)}</Badge>
                  </Table.Td>
                  <Table.Td className="num" ta="right" fw={600} c={m.qty_delta < 0 ? "red" : "green"}>
                    {m.qty_delta > 0 ? `+${m.qty_delta}` : m.qty_delta}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" className="num">
                      #{m.source_ref.slice(0, 8)}
                    </Text>
                    {m.note && (
                      <Text size="xs" c="dimmed">
                        {m.note}
                      </Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          )}
        </Table>
      )}
      {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
    </Stack>
  );
}

function AdjustForm({ branchId, row, onDone }: { branchId: string; row: StockRow; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [delta, setDelta] = useState<number | string>("");
  const [note, setNote] = useState("");
  const qty = typeof delta === "number" ? delta : NaN;
  const valid = Number.isInteger(qty) && qty !== 0 && note.trim() !== "";
  const adjust = useMutation({
    mutationFn: () =>
      api<StockRow>("/inventory/adjustments", {
        method: "POST",
        json: { branch_id: branchId, sku: row.sku, qty_delta: qty, note: note.trim() },
      }),
    onSuccess: (r) => {
      notifications.show({ color: "green", message: `${r.sku} now has ${r.on_hand} on hand` });
      for (const key of ["stock", "movements", "stock-count"]) {
        queryClient.invalidateQueries({ queryKey: [key, branchId] });
      }
      onDone();
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (valid) adjust.mutate();
  }

  return (
    <form onSubmit={onSubmit}>
      <Stack>
        {adjust.error && <Alert color="red">{adjust.error.message}</Alert>}
        <Text size="sm" c="dimmed">
          {row.name || row.sku} has {row.on_hand} on hand. Enter a positive number to add stock or a negative number to
          remove it.
        </Text>
        <NumberInput
          label="Change"
          placeholder="-3"
          required
          allowDecimal={false}
          value={delta}
          onChange={setDelta}
          description={Number.isInteger(qty) && qty !== 0 ? `On hand becomes ${row.on_hand + qty}` : undefined}
        />
        <TextInput
          label="Note"
          placeholder="Count after breakage"
          required
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
        <Button type="submit" loading={adjust.isPending} disabled={!valid} mt="xs">
          Save adjustment
        </Button>
      </Stack>
    </form>
  );
}
