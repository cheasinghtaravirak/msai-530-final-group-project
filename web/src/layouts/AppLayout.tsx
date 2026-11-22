import { AppShell, Badge, Burger, Button, Group, NavLink, ScrollArea, Stack, Text, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { NavLink as RouterLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { hasRole, type Role } from "../auth/roles";

interface NavItem {
  label: string;
  to: string;
  roles: Role[];
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Headquarters",
    items: [
      { label: "Company dashboard", to: "/hq", roles: ["HQ_ADMIN"] },
      { label: "Branches", to: "/hq/branches", roles: ["HQ_ADMIN"] },
      { label: "Jobs", to: "/hq/jobs", roles: ["HQ_ADMIN"] },
    ],
  },
  {
    section: "Branch",
    items: [{ label: "Branch dashboard", to: "/branch", roles: ["HQ_ADMIN", "BRANCH_MANAGER"] }],
  },
  {
    section: "Point of sale",
    items: [{ label: "Sell", to: "/pos", roles: ["BRANCH_MANAGER", "CASHIER"] }],
  },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const [opened, { toggle, close }] = useDisclosure();
  const location = useLocation();

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: "sm", collapsed: { mobile: !opened } }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <Title order={4}>Retail Ops</Title>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Text size="sm" visibleFrom="xs" truncate>
              {user?.full_name}
            </Text>
            <Button variant="subtle" size="xs" onClick={logout}>
              Log out
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <ScrollArea>
          <Stack gap="md">
            {NAV.map(({ section, items }) => {
              const visible = items.filter((i) => hasRole(user, i.roles));
              if (visible.length === 0) return null;
              return (
                <div key={section}>
                  <Text size="xs" fw={600} c="dimmed" tt="uppercase" px="sm" mb={4}>
                    {section}
                  </Text>
                  {visible.map((item) => (
                    <NavLink
                      key={item.to}
                      component={RouterLink}
                      to={item.to}
                      end
                      label={item.label}
                      active={location.pathname === item.to}
                      onClick={close}
                    />
                  ))}
                </div>
              );
            })}
          </Stack>
        </ScrollArea>
        <Group gap={4} mt="auto" pt="sm">
          {user?.roles.map((g) => (
            <Badge key={`${g.role}-${g.branch_id}`} variant="light" size="sm">
              {g.role}
              {g.branch_id ? ` · ${g.branch_id}` : ""}
            </Badge>
          ))}
        </Group>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
