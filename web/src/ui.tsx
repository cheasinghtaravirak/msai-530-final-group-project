import { Alert, Button, Card, Group, Skeleton, Stack, Table, Text, ThemeIcon, Title } from "@mantine/core";
import { IconRefresh, type Icon } from "@tabler/icons-react";
import type { ReactNode } from "react";

/** "PHNOM_PENH" -> "Phnom Penh", "DONE" -> "Done". */
export function humanize(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const USD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/** "1.70" -> "$1.70". */
export function formatMoney(amount: string): string {
  return USD.format(Number(amount));
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <Group justify="space-between" align="flex-end" gap="md" className="page-header">
      <Stack gap={4}>
        <Title order={1}>{title}</Title>
        {description && (
          <Text c="dimmed" className="measure">
            {description}
          </Text>
        )}
      </Stack>
      {actions && <Group gap="xs">{actions}</Group>}
    </Group>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Card>
      <Text size="sm" fw={500} c="dimmed">
        {label}
      </Text>
      <Text component="div" className="stat-value" mt={6}>
        {value}
      </Text>
      {hint && (
        <Text size="sm" c="dimmed" mt={4}>
          {hint}
        </Text>
      )}
    </Card>
  );
}

export function EmptyState({
  icon: IconComponent,
  title,
  children,
  action,
}: {
  icon: Icon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Stack align="center" gap="xs" py={{ base: "sm", sm: "xl" }} px="md" ta="center">
      <ThemeIcon size={44} radius="lg" variant="light">
        <IconComponent size={24} stroke={1.6} />
      </ThemeIcon>
      <Title order={3} mt={6}>
        {title}
      </Title>
      {children && (
        <Text c="dimmed" maw="44ch">
          {children}
        </Text>
      )}
      {action && <div className="empty-action">{action}</div>}
    </Stack>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Alert color="red" title="Couldn't load this data" radius="md">
      <Stack gap="sm" align="flex-start">
        <Text size="sm">{error instanceof Error ? error.message : "Check your connection and try again."}</Text>
        {onRetry && (
          <Button size="xs" variant="white" color="red" leftSection={<IconRefresh size={14} />} onClick={onRetry}>
            Try again
          </Button>
        )}
      </Stack>
    </Alert>
  );
}

export function TableSkeleton({ columns, rows = 4 }: { columns: number; rows?: number }) {
  return (
    <Table.Tbody aria-busy="true">
      {Array.from({ length: rows }, (_, r) => (
        <Table.Tr key={r}>
          {Array.from({ length: columns }, (_, c) => (
            <Table.Td key={c}>
              <Skeleton height={12} radius="sm" width={c === 0 ? "60%" : "80%"} />
            </Table.Td>
          ))}
        </Table.Tr>
      ))}
    </Table.Tbody>
  );
}
