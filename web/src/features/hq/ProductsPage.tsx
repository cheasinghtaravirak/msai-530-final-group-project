import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconPackage, IconSearch } from "@tabler/icons-react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "../../api/client";
import { EmptyState, ErrorState, formatMoney, humanize, PageHeader, TableSkeleton } from "../../ui";
import { useBranches } from "./BranchesPage";

interface Category {
  category_id: string;
  parent_id: string | null;
  name: string;
}

type ProductStatus = "ACTIVE" | "DISCONTINUED";

interface Sku {
  sku: string;
  name: string;
  barcode: string;
  unit: string;
  pack_size: number;
  /** Today's company-wide (ALL) price. */
  price: string | null;
}

interface Product {
  product_id: string;
  category_id: string;
  category: string;
  name: string;
  brand: string;
  status: ProductStatus;
  skus: Sku[];
}

interface PriceRow {
  sku: string;
  branch_scope: string;
  valid_from: string;
  amount: string;
}

interface SkuDetail extends Omit<Sku, "price"> {
  product_id: string;
  prices: PriceRow[];
}

const PAGE_SIZE = 50;
const COLUMNS = ["Product", "SKU", "Barcode", "Category", "Status", "Price", ""];
const STATUS_OPTIONS = (["ACTIVE", "DISCONTINUED"] as const).map((s) => ({ value: s, label: humanize(s) }));

function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: () =>
      api<{ results: Category[] }>("/catalog/categories?page_size=500").then((r) =>
        r.results.map((c) => ({ value: c.category_id, label: c.name })),
      ),
  });
}

function useProducts(q: string, categoryId: string | null, page: number) {
  return useQuery({
    queryKey: ["products", { q, categoryId, page }],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (q) params.set("q", q);
      if (categoryId) params.set("category_id", categoryId);
      return api<{ results: Product[]; count: number }>(`/catalog/products?${params}`);
    },
    placeholderData: keepPreviousData,
  });
}

export function ProductsPage() {
  const [search, setSearch] = useState("");
  const [q] = useDebouncedValue(search.trim(), 300);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const categories = useCategories();
  const { data, isLoading, error, refetch } = useProducts(q, categoryId, page);
  const [editing, setEditing] = useState<Product | null>(null);
  const [pricing, setPricing] = useState<Sku | null>(null);
  const pages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  return (
    <Stack gap="xl">
      <PageHeader
        title="Products"
        description="The company catalogue, one row per SKU, with today's company-wide price."
      />
      <Group gap="sm" align="flex-end">
        <TextInput
          aria-label="Search products"
          placeholder="Name, brand, SKU or barcode"
          leftSection={<IconSearch size={16} stroke={1.6} />}
          w={320}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value);
            setPage(1);
          }}
        />
        <Select
          aria-label="Category"
          placeholder="All categories"
          data={categories.data ?? []}
          value={categoryId}
          clearable
          searchable
          w={220}
          onChange={(v) => {
            setCategoryId(v);
            setPage(1);
          }}
        />
      </Group>
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {data?.count === 0 ? (
        <Card>
          <EmptyState icon={IconPackage} title="No products found">
            {q || categoryId ? "Try another search or category." : "Products added to the catalogue appear here."}
          </EmptyState>
        </Card>
      ) : (
        (isLoading || data) && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={760} type="native">
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
                    {data?.results.flatMap((p) =>
                      p.skus.map((s) => (
                        <Table.Tr key={s.sku}>
                          <Table.Td>
                            <Text inherit fw={600}>
                              {p.name}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {s.name}
                            </Text>
                          </Table.Td>
                          <Table.Td>{s.sku}</Table.Td>
                          <Table.Td className="num" c="dimmed">
                            {s.barcode || "None"}
                          </Table.Td>
                          <Table.Td>{p.category}</Table.Td>
                          <Table.Td>
                            <Badge color={p.status === "ACTIVE" ? "green" : "gray"}>{humanize(p.status)}</Badge>
                          </Table.Td>
                          <Table.Td className="num">
                            {s.price ? formatMoney(s.price) : <Badge color="gray">No price</Badge>}
                          </Table.Td>
                          <Table.Td ta="right">
                            <Group gap={4} justify="flex-end" wrap="nowrap">
                              <Button
                                size="xs"
                                variant="subtle"
                                aria-label={`Price for ${s.sku}`}
                                onClick={() => setPricing(s)}
                              >
                                Price
                              </Button>
                              <Button
                                size="xs"
                                variant="subtle"
                                color="gray"
                                aria-label={`Edit ${p.name}`}
                                onClick={() => setEditing(p)}
                              >
                                Edit
                              </Button>
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      )),
                    )}
                  </Table.Tbody>
                )}
              </Table>
            </Table.ScrollContainer>
          </Card>
        )
      )}
      {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={<Text fw={600}>Edit product</Text>}>
        {editing && (
          <EditProductForm product={editing} categories={categories.data ?? []} onDone={() => setEditing(null)} />
        )}
      </Modal>
      <Modal
        opened={pricing !== null}
        onClose={() => setPricing(null)}
        size="lg"
        title={<Text fw={600}>Prices for {pricing?.sku}</Text>}
      >
        {pricing && <PriceEditor sku={pricing} />}
      </Modal>
    </Stack>
  );
}

function EditProductForm({
  product,
  categories,
  onDone,
}: {
  product: Product;
  categories: { value: string; label: string }[];
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: product.name,
    brand: product.brand,
    category_id: product.category_id,
    status: product.status,
  });
  const save = useMutation({
    mutationFn: () => api<Product>(`/catalog/products/${product.product_id}`, { method: "PATCH", json: form }),
    onSuccess: (p) => {
      notifications.show({ color: "green", message: `${p.name} saved` });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      onDone();
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={onSubmit}>
      <Stack>
        {save.error && <Alert color="red">{save.error.message}</Alert>}
        <TextInput
          label="Name"
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
        />
        <TextInput
          label="Brand"
          value={form.brand}
          onChange={(e) => setForm({ ...form, brand: e.currentTarget.value })}
        />
        <Select
          label="Category"
          data={categories}
          value={form.category_id}
          allowDeselect={false}
          searchable
          onChange={(v) => v && setForm({ ...form, category_id: v })}
        />
        <Select
          label="Status"
          data={STATUS_OPTIONS}
          value={form.status}
          allowDeselect={false}
          onChange={(v) => v && setForm({ ...form, status: v as ProductStatus })}
        />
        <Button type="submit" loading={save.isPending} mt="xs">
          Save product
        </Button>
      </Stack>
    </form>
  );
}

// Today in the company's time zone, which the services price by; en-CA gives the YYYY-MM-DD a date input expects.
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Phnom_Penh" });

function PriceEditor({ sku }: { sku: Sku }) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["sku", sku.sku],
    queryFn: () => api<SkuDetail>(`/catalog/skus/${sku.sku}`),
  });
  const branches = useBranches();
  const scopes = ["ALL", ...(branches.data ?? []).filter((b) => b.status === "OPEN").map((b) => b.branch_id)];
  const [scope, setScope] = useState("ALL");
  const [amount, setAmount] = useState<number | string>(sku.price ? Number(sku.price) : "");
  const [validFrom, setValidFrom] = useState(today);
  const save = useMutation({
    mutationFn: (value: number) =>
      api<PriceRow>(`/catalog/prices/${sku.sku}`, {
        method: "PUT",
        json: { branch_scope: scope, amount: value.toFixed(2), valid_from: validFrom },
      }),
    onSuccess: (row) => {
      notifications.show({
        color: "green",
        message: `${row.sku} is ${formatMoney(row.amount)} at ${row.branch_scope === "ALL" ? "all branches" : row.branch_scope} from ${row.valid_from}`,
      });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["sku", sku.sku] });
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (typeof amount === "number") save.mutate(amount);
  }

  const rows = [...(detail.data?.prices ?? [])].sort(
    (a, b) => b.valid_from.localeCompare(a.valid_from) || a.branch_scope.localeCompare(b.branch_scope),
  );

  return (
    <Stack gap="lg">
      <Text size="sm" c="dimmed">
        {sku.name}. A branch price beats the ALL price; the latest valid-from date on or before today wins.
      </Text>
      {detail.error ? (
        <ErrorState error={detail.error} onRetry={() => detail.refetch()} />
      ) : (
        <Table>
          <Table.Thead className="table-head">
            <Table.Tr>
              <Table.Th>Scope</Table.Th>
              <Table.Th>Valid from</Table.Th>
              <Table.Th ta="right">Amount</Table.Th>
            </Table.Tr>
          </Table.Thead>
          {detail.isLoading ? (
            <TableSkeleton columns={3} rows={2} />
          ) : (
            <Table.Tbody>
              {rows.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={3} c="dimmed">
                    No prices yet.
                  </Table.Td>
                </Table.Tr>
              )}
              {rows.map((r) => (
                <Table.Tr key={`${r.branch_scope}-${r.valid_from}`}>
                  <Table.Td>{r.branch_scope}</Table.Td>
                  <Table.Td className="num">{r.valid_from}</Table.Td>
                  <Table.Td className="num" ta="right">
                    {formatMoney(r.amount)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          )}
        </Table>
      )}
      <form onSubmit={onSubmit}>
        <Stack>
          {save.error && <Alert color="red">{save.error.message}</Alert>}
          <Group grow align="flex-start">
            <Select
              label="Scope"
              data={scopes}
              value={scope}
              allowDeselect={false}
              onChange={(v) => v && setScope(v)}
            />
            <NumberInput
              label="Amount"
              required
              min={0}
              decimalScale={2}
              fixedDecimalScale
              leftSection="$"
              value={amount}
              onChange={setAmount}
            />
            <TextInput
              label="Valid from"
              type="date"
              required
              value={validFrom}
              onChange={(e) => setValidFrom(e.currentTarget.value)}
            />
          </Group>
          <Button type="submit" loading={save.isPending} disabled={typeof amount !== "number"}>
            Save price
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}
