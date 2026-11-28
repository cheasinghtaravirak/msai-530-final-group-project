import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconBuildingStore, IconChevronDown, IconChevronRight, IconReceipt } from "@tabler/icons-react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";

import { api } from "../../api/client";
import type { Order, Page } from "../../api/types";
import { useBranch } from "../../auth/BranchContext";
import {
  EmptyState,
  ErrorState,
  formatDateTime,
  formatMoney,
  formatTime,
  PageHeader,
  TableSkeleton,
  today,
} from "../../ui";
import { METHOD_LABEL } from "../pos/PosPage";

const PAGE_SIZE = 50;

function NoBranch({ title }: { title: string }) {
  return (
    <Stack gap="xl">
      <PageHeader title={title} />
      <Card>
        <EmptyState icon={IconBuildingStore} title="No branch to show">
          Your account has no role at a branch for this page.
        </EmptyState>
      </Card>
    </Stack>
  );
}

export function TodaysSalesPage() {
  const { branchId } = useBranch();
  if (!branchId) return <NoBranch title="Today's sales" />;
  return (
    <Stack gap="xl">
      <PageHeader title="Today's sales" description={`Sales at ${branchId} today, newest first.`} />
      <OrdersTable branchId={branchId} date={today()} refundable={false} />
    </Stack>
  );
}

export function SalesHistoryPage() {
  const { branchId } = useBranch();
  const [date, setDate] = useState(today);
  if (!branchId) return <NoBranch title="Sales history" />;
  return (
    <Stack gap="xl">
      <PageHeader
        title="Sales history"
        description={`Every sale at ${branchId} on the chosen day. Refund a completed sale here.`}
      />
      <TextInput
        label="Sale date"
        type="date"
        w={200}
        max={today()}
        value={date}
        onChange={(e) => e.currentTarget.value && setDate(e.currentTarget.value)}
      />
      <OrdersTable key={date} branchId={branchId} date={date} refundable />
    </Stack>
  );
}

function OrdersTable({ branchId, date, refundable }: { branchId: string; date: string; refundable: boolean }) {
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [refunding, setRefunding] = useState<Order | null>(null);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["orders", branchId, date, page],
    queryFn: () => {
      const params = new URLSearchParams({
        branch_id: branchId,
        date,
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      return api<Page<Order>>(`/order/orders?${params}`);
    },
    placeholderData: keepPreviousData,
  });
  const pages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);
  const columns = ["", "Time", "Order", "Items", "Total", "Status", ...(refundable ? [""] : [])];

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (data?.count === 0) {
    return (
      <Card>
        <EmptyState icon={IconReceipt} title="No sales yet">
          {date === today() ? "Sales rung up at this branch today appear here." : `No sales at ${branchId} on ${date}.`}
        </EmptyState>
      </Card>
    );
  }

  return (
    <>
      <Card padding={0}>
        <Table.ScrollContainer minWidth={560} type="native">
          <Table highlightOnHover>
            <Table.Thead className="table-head">
              <Table.Tr>
                {columns.map((c, i) => (
                  <Table.Th key={i} ta={c === "Items" || c === "Total" ? "right" : undefined}>
                    {c}
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            {isLoading ? (
              <TableSkeleton columns={columns.length} />
            ) : (
              <Table.Tbody>
                {data?.results.map((o) => {
                  const expanded = open === o.order_id;
                  const short = o.order_id.slice(0, 8);
                  return (
                    <Fragment key={o.order_id}>
                      <Table.Tr style={{ cursor: "pointer" }} onClick={() => setOpen(expanded ? null : o.order_id)}>
                        <Table.Td w={40}>
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={`${expanded ? "Hide" : "Show"} lines of order ${short}`}
                            aria-expanded={expanded}
                          >
                            {expanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
                          </ActionIcon>
                        </Table.Td>
                        <Table.Td className="num">{formatTime(o.completed_at)}</Table.Td>
                        <Table.Td className="num" fw={600}>
                          #{short}
                        </Table.Td>
                        <Table.Td className="num" ta="right">
                          {o.lines.reduce((n, l) => n + l.qty, 0)}
                        </Table.Td>
                        <Table.Td className="num" ta="right" fw={600}>
                          {formatMoney(o.total_amount)}
                        </Table.Td>
                        <Table.Td>
                          <Badge color={o.status === "COMPLETED" ? "green" : "orange"}>
                            {o.status === "COMPLETED" ? "Completed" : "Refunded"}
                          </Badge>
                        </Table.Td>
                        {refundable && (
                          <Table.Td ta="right">
                            {o.status === "COMPLETED" && (
                              <Button
                                size="xs"
                                variant="subtle"
                                color="red"
                                aria-label={`Refund order ${short}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRefunding(o);
                                }}
                              >
                                Refund
                              </Button>
                            )}
                          </Table.Td>
                        )}
                      </Table.Tr>
                      {expanded && (
                        <Table.Tr>
                          <Table.Td />
                          <Table.Td colSpan={columns.length - 1}>
                            <OrderDetail order={o} />
                          </Table.Td>
                        </Table.Tr>
                      )}
                    </Fragment>
                  );
                })}
              </Table.Tbody>
            )}
          </Table>
        </Table.ScrollContainer>
      </Card>
      {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
      <Modal opened={refunding !== null} onClose={() => setRefunding(null)} title={<Text fw={600}>Refund sale</Text>}>
        {refunding && <RefundConfirm order={refunding} onDone={() => setRefunding(null)} />}
      </Modal>
    </>
  );
}

function OrderDetail({ order }: { order: Order }) {
  return (
    <Stack gap="xs" py={4}>
      <Table withRowBorders={false} verticalSpacing={4}>
        <Table.Tbody>
          {order.lines.map((l) => (
            <Table.Tr key={l.line_no}>
              <Table.Td>
                {l.name}{" "}
                <Text span size="xs" c="dimmed">
                  {l.sku}
                </Text>
              </Table.Td>
              <Table.Td className="num" ta="right" c="dimmed">
                {l.qty} × {formatMoney(l.unit_price)}
              </Table.Td>
              <Table.Td className="num" ta="right">
                {formatMoney(l.line_total)}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Text size="sm" c="dimmed">
        Paid by {order.payments.map((p) => METHOD_LABEL[p.method]).join(", ")}. Order {order.order_id}.
        {order.refunded_at && ` Refunded ${formatDateTime(order.refunded_at)}.`}
      </Text>
    </Stack>
  );
}

function RefundConfirm({ order, onDone }: { order: Order; onDone: () => void }) {
  const queryClient = useQueryClient();
  const refund = useMutation({
    mutationFn: () => api<Order>(`/order/orders/${order.order_id}/refund`, { method: "POST" }),
    onSuccess: (o) => {
      notifications.show({ color: "green", message: `Order #${o.order_id.slice(0, 8)} refunded` });
      for (const key of ["orders", "sales-report", "stock", "movements"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      onDone();
    },
  });

  return (
    <Stack>
      {refund.error && <Alert color="red">{refund.error.message}</Alert>}
      <Text>
        Refund order #{order.order_id.slice(0, 8)} for {formatMoney(order.total_amount)}? The whole sale is refunded and
        its items go back into stock.
      </Text>
      <Group justify="flex-end" gap="xs">
        <Button variant="default" onClick={onDone}>
          Cancel
        </Button>
        <Button color="red" loading={refund.isPending} onClick={() => refund.mutate()}>
          Refund {formatMoney(order.total_amount)}
        </Button>
      </Group>
    </Stack>
  );
}
