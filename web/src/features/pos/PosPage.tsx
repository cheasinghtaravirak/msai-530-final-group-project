import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  NumberInput,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconBarcode, IconBuildingStore, IconMinus, IconPlus, IconSearch, IconTrash } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from "react";

import { api, ApiError, apiResponse } from "../../api/client";
import type { Order, Page, PaymentMethod, PosItem } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { useBranch } from "../../auth/BranchContext";
import { fromCents, toCents } from "../../money";
import { EmptyState, ErrorState, formatMoney, formatTime, PageHeader, TableSkeleton } from "../../ui";
import {
  canSubmit,
  cartTotal,
  IDLE,
  orderRequest,
  saleReducer,
  tenderedCents,
  type CartLine,
  type Failure,
  type Sale,
  type SaleAction,
  type Tender,
} from "./sale";

const BARCODE = /^\d{8,}$/;
const SEARCH_COLUMNS = ["Item", "SKU", "Price", ""];
export const METHOD_LABEL: Record<PaymentMethod, string> = { CASH: "Cash", CARD: "Card", QR: "QR" };
const METHODS = (Object.keys(METHOD_LABEL) as PaymentMethod[]).map((m) => ({ value: m, label: METHOD_LABEL[m] }));

const money = (cents: number) => formatMoney(fromCents(cents));
const sentence = (text: string) => (/[.!?]$/.test(text) ? text : `${text}.`);

function useItemSearch(branchId: string, q: string) {
  return useQuery({
    queryKey: ["pos-items", branchId, q],
    queryFn: () => {
      const params = new URLSearchParams({ branch_id: branchId, q, page_size: "20" });
      return api<Page<PosItem>>(`/order/pos/items?${params}`);
    },
    enabled: q !== "",
    // Overrides the app's 10 s cache: HQ can change a price while the till is open.
    staleTime: 0,
    retry: false,
  });
}

// A sale outlives a reload or a trip to Today's sales, so a retry after a lost response keeps its order id.
function useSale(userId: string, branchId: string) {
  const key = `retail.sale.${userId}.${branchId}`;
  const [sale, dispatch] = useReducer(saleReducer, key, (k): Sale => {
    try {
      const raw = sessionStorage.getItem(k);
      const saved = raw ? (JSON.parse(raw) as Sale) : IDLE;
      if (saved.step !== "submitting") return saved;
      const failure: Failure = {
        kind: "error",
        message: "The last attempt was interrupted before the till heard back.",
      };
      return { ...saved, step: "cart", failure };
    } catch {
      return IDLE;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(sale));
    } catch {
      /* storage unavailable: the sale lasts until reload */
    }
  }, [key, sale]);
  return [sale, dispatch] as const;
}

function failedAction(error: unknown): SaleAction {
  if (!(error instanceof ApiError)) return { type: "failed", failure: { kind: "error", message: String(error) } };
  const details = (error.details ?? {}) as { sku?: string; lines?: { sku: string; unit_price: string }[] };
  if (error.code === "PAYMENT_MISMATCH") {
    return { type: "failed", failure: { kind: "prices_changed" }, prices: details.lines };
  }
  if ((error.code === "PRICE_UNAVAILABLE" || error.code === "ITEM_NOT_FOUND") && details.sku) {
    return { type: "failed", failure: { kind: "item", sku: details.sku, message: error.message } };
  }
  return { type: "failed", failure: { kind: "error", message: error.message } };
}

export function PosPage() {
  const { branchId } = useBranch();
  if (!branchId) {
    return (
      <Stack gap="xl">
        <PageHeader title="Sell" />
        <Card>
          <EmptyState icon={IconBuildingStore} title="No till to sell at">
            Your account has no cashier or manager role at a branch.
          </EmptyState>
        </Card>
      </Stack>
    );
  }
  return <Till key={branchId} branchId={branchId} />;
}

function Till({ branchId }: { branchId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [sale, dispatch] = useSale(user?.user_id ?? "", branchId);

  async function complete() {
    if (sale.step !== "cart" || !canSubmit(sale)) return;
    dispatch({ type: "submit" });
    try {
      const { status, body: order } = await apiResponse<Order>("/order/orders", {
        method: "POST",
        json: orderRequest(sale, branchId),
      });
      dispatch({ type: "succeeded", order, replayed: status === 200 });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    } catch (error) {
      dispatch(failedAction(error));
    }
  }

  return (
    <Stack gap="xl">
      <PageHeader title="Sell" description={`Selling at ${branchId}.`} />
      {sale.step === "receipt" ? (
        <Receipt sale={sale} onNewSale={() => dispatch({ type: "new_sale" })} />
      ) : (
        <Grid gutter="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="lg">
              <ItemLookup
                branchId={branchId}
                disabled={sale.step === "submitting"}
                onAdd={(line) => dispatch({ type: "add", line, newOrderId: crypto.randomUUID() })}
              />
              <Cart sale={sale} dispatch={dispatch} />
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            {sale.step !== "idle" && <PaymentPanel sale={sale} dispatch={dispatch} onComplete={complete} />}
          </Grid.Col>
        </Grid>
      )}
    </Stack>
  );
}

function ItemLookup({
  branchId,
  disabled,
  onAdd,
}: {
  branchId: string;
  disabled: boolean;
  onAdd: (line: Omit<CartLine, "qty">) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [q] = useDebouncedValue(text.trim(), 300);
  const [problem, setProblem] = useState<string | null>(null);
  const search = useItemSearch(branchId, BARCODE.test(q) ? "" : q);

  function add(item: PosItem) {
    const unitCents = item.unit_price === null ? null : toCents(item.unit_price);
    if (unitCents === null) {
      setProblem(`${item.name} has no price at ${branchId} yet, so it can't be sold.`);
      return;
    }
    onAdd({ sku: item.sku, name: item.name, unitCents });
    setText("");
    setProblem(null);
    input.current?.focus();
  }

  async function scan(barcode: string) {
    setText("");
    try {
      const params = new URLSearchParams({ branch_id: branchId, barcode });
      add(await api<PosItem>(`/order/pos/items?${params}`));
    } catch (error) {
      const notFound = error instanceof ApiError && error.code === "ITEM_NOT_FOUND";
      setProblem(notFound ? `Nothing has barcode ${barcode}.` : (error as Error).message);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const value = e.currentTarget.value.trim();
    if (BARCODE.test(value)) scan(value);
    else if (value === q && search.data?.results.length === 1) add(search.data.results[0]);
  }

  const results = q && !BARCODE.test(q) && text.trim() ? search : null;

  return (
    <Stack gap="xs">
      <TextInput
        ref={input}
        aria-label="Scan or search"
        placeholder="Scan a barcode or type a name or SKU"
        size="lg"
        leftSection={<IconSearch size={18} stroke={1.6} />}
        autoFocus
        disabled={disabled}
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        onKeyDown={onKeyDown}
      />
      {problem && (
        <Alert color="yellow" withCloseButton closeButtonLabel="Dismiss" onClose={() => setProblem(null)}>
          {problem}
        </Alert>
      )}
      {results?.error && <ErrorState error={results.error} onRetry={() => results.refetch()} />}
      {results?.data?.count === 0 && (
        <Text size="sm" c="dimmed">
          Nothing matches “{q}”. Try another name or SKU.
        </Text>
      )}
      {results && !results.error && results.data?.count !== 0 && (
        <Card padding={0}>
          <Table.ScrollContainer minWidth={420} type="native">
            <Table highlightOnHover>
              <Table.Thead className="table-head">
                <Table.Tr>
                  {SEARCH_COLUMNS.map((c) => (
                    <Table.Th key={c} ta={c === "Price" ? "right" : undefined}>
                      {c}
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              {!results.data ? (
                <TableSkeleton columns={SEARCH_COLUMNS.length} rows={3} />
              ) : (
                <Table.Tbody>
                  {results.data.results.map((item) => (
                    <Table.Tr key={item.sku}>
                      <Table.Td fw={600}>{item.name}</Table.Td>
                      <Table.Td c="dimmed">{item.sku}</Table.Td>
                      <Table.Td className="num" ta="right" fw={600}>
                        {item.unit_price ? formatMoney(item.unit_price) : <Badge color="gray">No price</Badge>}
                      </Table.Td>
                      <Table.Td ta="right">
                        <Button
                          size="xs"
                          variant="light"
                          disabled={item.unit_price === null}
                          aria-label={`Add ${item.name}`}
                          onClick={() => add(item)}
                        >
                          Add
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              )}
            </Table>
          </Table.ScrollContainer>
          {results.data && results.data.count > results.data.results.length && (
            <Text size="sm" c="dimmed" px="md" py="sm">
              Showing {results.data.results.length} of {results.data.count}. Type more to narrow the list.
            </Text>
          )}
        </Card>
      )}
    </Stack>
  );
}

function Cart({ sale, dispatch }: { sale: Sale; dispatch: (a: SaleAction) => void }) {
  if (sale.step !== "cart" && sale.step !== "submitting") {
    return (
      <Card py="xl">
        <EmptyState icon={IconBarcode} title="Scan or search for an item">
          Scan a barcode, or type part of a name or SKU and pick the item. It goes straight into the cart.
        </EmptyState>
      </Card>
    );
  }
  const locked = sale.step === "submitting";
  const badSku = sale.step === "cart" && sale.failure?.kind === "item" ? sale.failure.sku : null;
  return (
    <Card padding={0}>
      <Table.ScrollContainer minWidth={520} type="native">
        <Table>
          <Table.Thead className="table-head">
            <Table.Tr>
              <Table.Th>Item</Table.Th>
              <Table.Th ta="right">Price</Table.Th>
              <Table.Th ta="center">Qty</Table.Th>
              <Table.Th ta="right">Total</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sale.lines.map((l) => (
              <Table.Tr key={l.sku} bg={l.sku === badSku ? "var(--mantine-color-red-light)" : undefined}>
                <Table.Td>
                  <Text inherit fw={600}>
                    {l.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {l.sku}
                  </Text>
                </Table.Td>
                <Table.Td className="num" ta="right">
                  {money(l.unitCents)}
                </Table.Td>
                <Table.Td>
                  <Group gap={6} justify="center" wrap="nowrap">
                    <ActionIcon
                      variant="default"
                      aria-label={`One fewer ${l.name}`}
                      disabled={locked || l.qty <= 1}
                      onClick={() => dispatch({ type: "set_qty", sku: l.sku, qty: l.qty - 1 })}
                    >
                      <IconMinus size={14} />
                    </ActionIcon>
                    <Text className="num" fw={600} miw={24} ta="center">
                      {l.qty}
                    </Text>
                    <ActionIcon
                      variant="default"
                      aria-label={`One more ${l.name}`}
                      disabled={locked}
                      onClick={() => dispatch({ type: "set_qty", sku: l.sku, qty: l.qty + 1 })}
                    >
                      <IconPlus size={14} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
                <Table.Td className="num" ta="right" fw={600}>
                  {money(l.unitCents * l.qty)}
                </Table.Td>
                <Table.Td ta="right">
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    aria-label={`Remove ${l.name}`}
                    disabled={locked}
                    onClick={() => dispatch({ type: "remove", sku: l.sku })}
                  >
                    <IconTrash size={16} stroke={1.6} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  );
}

function FailureAlert({ failure }: { failure: Failure }) {
  switch (failure.kind) {
    case "prices_changed":
      return (
        <Alert color="yellow" title="Prices changed">
          A price changed since the items were scanned. The cart now shows the current prices. Check the new total with
          the customer, then complete the sale again.
        </Alert>
      );
    case "item":
      return (
        <Alert color="red" title={`Can't sell ${failure.sku}`}>
          {sentence(failure.message)} Remove it from the cart and complete the sale again.
        </Alert>
      );
    case "error":
      return (
        <Alert color="red" title="The sale did not go through">
          {sentence(failure.message)} The cart is kept. Completing the sale again will not record it twice.
        </Alert>
      );
  }
}

function PaymentPanel({
  sale,
  dispatch,
  onComplete,
}: {
  sale: Extract<Sale, { step: "cart" | "submitting" }>;
  dispatch: (a: SaleAction) => void;
  onComplete: () => void;
}) {
  const total = cartTotal(sale.lines);
  const cash = tenderedCents(sale.tender);
  const locked = sale.step === "submitting";
  const setTender = (tender: Partial<Tender>) => dispatch({ type: "tender", tender });

  return (
    <Card>
      <Stack gap="md">
        {sale.step === "cart" && sale.failure && <FailureAlert failure={sale.failure} />}
        <Group justify="space-between" align="baseline">
          <Text fw={500} c="dimmed">
            Total
          </Text>
          <Text className="stat-value">{money(total)}</Text>
        </Group>
        <SegmentedControl
          aria-label="Payment method"
          fullWidth
          data={METHODS}
          value={sale.tender.method}
          disabled={locked}
          onChange={(m) => setTender({ method: m as PaymentMethod })}
        />
        {sale.tender.method === "CASH" && (
          <>
            <Group align="flex-end" gap="xs" wrap="nowrap">
              <NumberInput
                label="Cash received"
                leftSection="$"
                min={0}
                decimalScale={2}
                hideControls
                inputMode="decimal"
                style={{ flex: 1 }}
                disabled={locked}
                value={sale.tender.tendered}
                onChange={(v) => setTender({ tendered: String(v) })}
              />
              <Button variant="default" disabled={locked} onClick={() => setTender({ tendered: fromCents(total) })}>
                Exact
              </Button>
            </Group>
            <Group justify="space-between">
              <Text c="dimmed">{cash !== null && cash < total ? "Still to pay" : "Change due"}</Text>
              <Text className="num" fw={600} size="lg">
                {cash === null ? "-" : money(Math.abs(cash - total))}
              </Text>
            </Group>
          </>
        )}
        <Button size="lg" loading={locked} disabled={!locked && !canSubmit(sale)} onClick={onComplete}>
          Complete sale
        </Button>
        <Button variant="subtle" color="gray" disabled={locked} onClick={() => dispatch({ type: "clear" })}>
          Clear cart
        </Button>
      </Stack>
    </Card>
  );
}

function Receipt({ sale, onNewSale }: { sale: Extract<Sale, { step: "receipt" }>; onNewSale: () => void }) {
  const { order, tender } = sale;
  const total = toCents(order.total_amount) ?? 0;
  const cash = tender.method === "CASH" ? tenderedCents(tender) : null;
  return (
    <Card maw={560}>
      <Stack gap="md">
        <Group justify="space-between" align="baseline">
          <Title order={2}>Sale complete</Title>
          <Text size="sm" c="dimmed" className="num">
            #{order.order_id.slice(0, 8)} · {formatTime(order.completed_at)}
          </Text>
        </Group>
        {(sale.replayed || total !== sale.chargedCents) && (
          <Alert color="yellow">
            The till had already recorded this sale, so nothing was charged twice. This receipt shows what was recorded.
          </Alert>
        )}
        <Table>
          <Table.Tbody>
            {order.lines.map((l) => (
              <Table.Tr key={l.line_no}>
                <Table.Td>
                  <Text inherit fw={500}>
                    {l.name}
                  </Text>
                  <Text size="xs" c="dimmed" className="num">
                    {l.qty} × {formatMoney(l.unit_price)}
                  </Text>
                </Table.Td>
                <Table.Td className="num" ta="right">
                  {formatMoney(l.line_total)}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group justify="space-between">
          <Text fw={600}>Total</Text>
          <Text className="num" fw={700} size="lg">
            {formatMoney(order.total_amount)}
          </Text>
        </Group>
        <Divider />
        <Group justify="space-between">
          <Text c="dimmed">Paid by</Text>
          <Text fw={500}>{METHOD_LABEL[tender.method]}</Text>
        </Group>
        {cash !== null && (
          <>
            <Group justify="space-between">
              <Text c="dimmed">Cash received</Text>
              <Text className="num">{money(cash)}</Text>
            </Group>
            <Group justify="space-between">
              <Text c="dimmed">Change</Text>
              <Text className="num" fw={600}>
                {money(Math.max(0, cash - total))}
              </Text>
            </Group>
          </>
        )}
        <Button size="lg" autoFocus onClick={onNewSale}>
          New sale
        </Button>
      </Stack>
    </Card>
  );
}
