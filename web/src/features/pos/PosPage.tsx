import { Card, Stack } from "@mantine/core";
import { IconBarcode } from "@tabler/icons-react";

import { useBranch } from "../../auth/BranchContext";
import { EmptyState, PageHeader } from "../../ui";

export function PosPage() {
  const { branchId } = useBranch();

  return (
    <Stack gap="xl">
      <PageHeader title="Sell" description={branchId ? `Selling at ${branchId}.` : undefined} />
      <Card py="xl">
        <EmptyState icon={IconBarcode} title="The register opens in Phase 3">
          Scan or search for products, build the cart, take cash, card or QR payment and print the receipt, all on this
          screen.
        </EmptyState>
      </Card>
    </Stack>
  );
}
