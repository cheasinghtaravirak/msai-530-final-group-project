import { Alert, Badge, Card, Stack, Table, Text, TextInput } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconBarcode, IconSearch } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState, type KeyboardEvent } from "react";

import { api, ApiError } from "../../api/client";
import { useBranch } from "../../auth/BranchContext";
import { EmptyState, ErrorState, formatMoney, PageHeader, TableSkeleton } from "../../ui";

interface PosItem {
  sku: string;
  name: string;
  unit_price: string | null;
}

type Lookup = { barcode: string } | { q: string };

const BARCODE = /^\d{8,}$/;
const COLUMNS = ["Item", "SKU", "Price"];

function usePosItems(branchId: string | null, lookup: Lookup | null) {
  return useQuery({
    queryKey: ["pos-items", branchId, lookup],
    queryFn: () => {
      if (lookup && "barcode" in lookup) {
        const params = new URLSearchParams({ branch_id: branchId!, barcode: lookup.barcode });
        return api<PosItem>(`/order/pos/items?${params}`).then((item) => ({ results: [item], count: 1 }));
      }
      const params = new URLSearchParams({ branch_id: branchId!, q: lookup!.q, page_size: "20" });
      return api<{ results: PosItem[]; count: number }>(`/order/pos/items?${params}`);
    },
    enabled: branchId !== null && lookup !== null,
    // Prices change at HQ while the till is open: never serve a cached price.
    staleTime: 0,
    refetchOnWindowFocus: true,
    retry: false,
  });
}

export function PosPage() {
  const { branchId } = useBranch();
  const [text, setText] = useState("");
  const [q] = useDebouncedValue(text.trim(), 300);
  const [barcode, setBarcode] = useState<string | null>(null);
  const lookup: Lookup | null = barcode ? { barcode } : q ? { q } : null;
  const { data, isFetching, error, refetch } = usePosItems(branchId, lookup);

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const value = e.currentTarget.value.trim();
    if (BARCODE.test(value)) {
      if (barcode === value) refetch();
      else setBarcode(value);
    } else if (value && value === q) {
      refetch();
    }
  }

  const notFound = error instanceof ApiError && error.code === "ITEM_NOT_FOUND";

  return (
    <Stack gap="xl">
      <PageHeader title="Sell" description={branchId ? `Selling at ${branchId}.` : undefined} />
      <Stack gap="xs">
        <TextInput
          aria-label="Scan or search"
          placeholder="Scan a barcode or type a name or SKU"
          size="lg"
          leftSection={<IconSearch size={18} stroke={1.6} />}
          autoFocus
          disabled={!branchId}
          value={text}
          onChange={(e) => {
            setText(e.currentTarget.value);
            setBarcode(null);
          }}
          onKeyDown={onKeyDown}
        />
        <Text size="sm" c="dimmed">
          Item lookup only. The cart and payment arrive in Phase 3.
        </Text>
      </Stack>
      {notFound ? (
        <Alert color="yellow" title="Item not found">
          Nothing has barcode {barcode}. Check the code, or search by name instead.
        </Alert>
      ) : (
        error && <ErrorState error={error} onRetry={() => refetch()} />
      )}
      {!lookup ? (
        <Card py="xl">
          <EmptyState icon={IconBarcode} title="Scan or search for an item">
            Scan a barcode and press Enter, or type part of a name or SKU to see the current price at this branch.
          </EmptyState>
        </Card>
      ) : data?.count === 0 ? (
        <Card>
          <EmptyState icon={IconSearch} title="No matching items">
            Nothing matches “{q}”. Try another name or SKU.
          </EmptyState>
        </Card>
      ) : (
        (isFetching || data) &&
        !error && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={420} type="native">
              <Table highlightOnHover>
                <Table.Thead className="table-head">
                  <Table.Tr>
                    {COLUMNS.map((c) => (
                      <Table.Th key={c} ta={c === "Price" ? "right" : undefined}>
                        {c}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                {!data ? (
                  <TableSkeleton columns={COLUMNS.length} rows={3} />
                ) : (
                  <Table.Tbody>
                    {data.results.map((item) => (
                      <Table.Tr key={item.sku}>
                        <Table.Td fw={600}>{item.name}</Table.Td>
                        <Table.Td c="dimmed">{item.sku}</Table.Td>
                        <Table.Td className="num" ta="right" fw={600}>
                          {item.unit_price ? formatMoney(item.unit_price) : <Badge color="gray">No price</Badge>}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                )}
              </Table>
            </Table.ScrollContainer>
            {data && data.count > data.results.length && (
              <Text size="sm" c="dimmed" px="md" py="sm">
                Showing {data.results.length} of {data.count}. Type more to narrow the list.
              </Text>
            )}
          </Card>
        )
      )}
    </Stack>
  );
}
