import { Stack, Text, Title } from "@mantine/core";

export function MessagePage({ title, text }: { title: string; text: string }) {
  return (
    <Stack gap="xs">
      <Title order={2}>{title}</Title>
      <Text c="dimmed">{text}</Text>
    </Stack>
  );
}
