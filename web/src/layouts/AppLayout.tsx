import {
  ActionIcon,
  AppShell,
  Avatar,
  Burger,
  Group,
  Menu,
  NavLink,
  ScrollArea,
  Select,
  Stack,
  Text,
  Tooltip,
  useMantineColorScheme,
  type MantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconBuildingStore,
  IconCashRegister,
  IconChartBar,
  IconCheck,
  IconClockPlay,
  IconDeviceDesktop,
  IconLayoutDashboard,
  IconLogout,
  IconMapPins,
  IconMoon,
  IconSun,
  IconSunMoon,
  type Icon,
} from "@tabler/icons-react";
import { NavLink as RouterLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useBranch } from "../auth/BranchContext";
import { hasRole, type Role } from "../auth/roles";

interface NavItem {
  label: string;
  to: string;
  icon: Icon;
  roles: Role[];
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Headquarters",
    items: [
      { label: "Company dashboard", to: "/hq", icon: IconLayoutDashboard, roles: ["HQ_ADMIN"] },
      { label: "Branches", to: "/hq/branches", icon: IconMapPins, roles: ["HQ_ADMIN"] },
      { label: "Scheduled jobs", to: "/hq/jobs", icon: IconClockPlay, roles: ["HQ_ADMIN"] },
    ],
  },
  {
    section: "Branch",
    items: [{ label: "Branch dashboard", to: "/branch", icon: IconChartBar, roles: ["HQ_ADMIN", "BRANCH_MANAGER"] }],
  },
  {
    section: "Point of sale",
    items: [{ label: "Sell", to: "/pos", icon: IconCashRegister, roles: ["BRANCH_MANAGER", "CASHIER"] }],
  },
];

const ROLE_LABEL: Record<Role, string> = {
  HQ_ADMIN: "HQ admin",
  BRANCH_MANAGER: "Branch manager",
  CASHIER: "Cashier",
  CUSTOMER: "Customer",
};

const APPEARANCE: { value: MantineColorScheme; label: string; icon: Icon }[] = [
  { value: "auto", label: "Automatic", icon: IconDeviceDesktop },
  { value: "light", label: "Light", icon: IconSun },
  { value: "dark", label: "Dark", icon: IconMoon },
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function AppearanceMenu() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  return (
    <Menu position="bottom-end" width={180}>
      <Menu.Target>
        <Tooltip label="Appearance" openDelay={400}>
          <ActionIcon variant="subtle" color="gray" size="lg" aria-label="Appearance">
            <IconSunMoon size={20} stroke={1.6} />
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Appearance</Menu.Label>
        {APPEARANCE.map(({ value, label, icon: ItemIcon }) => (
          <Menu.Item
            key={value}
            leftSection={<ItemIcon size={16} stroke={1.6} />}
            rightSection={colorScheme === value ? <IconCheck size={16} /> : null}
            onClick={() => setColorScheme(value)}
          >
            {label}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

function BranchControl() {
  const { branches, branchId, selectBranch } = useBranch();
  const icon = <IconBuildingStore size={16} stroke={1.6} />;
  if (branches.length > 1) {
    return (
      <Select
        aria-label="Branch"
        variant="filled"
        w={128}
        leftSection={icon}
        data={branches}
        value={branchId}
        allowDeselect={false}
        checkIconPosition="right"
        comboboxProps={{ transitionProps: { transition: "pop-top-right", duration: 120 } }}
        onChange={(id) => id && selectBranch(id)}
      />
    );
  }
  if (branchId) {
    return (
      <Group gap={6} c="dimmed" wrap="nowrap" aria-label="Branch">
        {icon}
        <Text size="sm" fw={500} className="num">
          {branchId}
        </Text>
      </Group>
    );
  }
  return null;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const [opened, { toggle, close }] = useDisclosure();
  const location = useLocation();

  return (
    <AppShell
      className="app-shell"
      header={{ height: 56 }}
      navbar={{ width: 248, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding={{ base: "md", sm: "xl" }}
      classNames={{ header: "chrome", navbar: "chrome chrome-sidebar", main: "app-main" }}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <div className="brand-mark">
              <Avatar radius="md" size={28} color="accent" variant="filled" aria-hidden>
                <IconBuildingStore size={17} stroke={1.8} />
              </Avatar>
              <Text inherit visibleFrom="xs">
                Retail Ops
              </Text>
            </div>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <BranchControl />
            <AppearanceMenu />
            <Menu position="bottom-end" width={240}>
              <Menu.Target>
                <ActionIcon variant="subtle" color="gray" size="lg" aria-label="Account">
                  <Avatar radius="md" size={30} color="accent">
                    {initials(user?.full_name ?? "")}
                  </Avatar>
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Stack gap={2} px="sm" py={8}>
                  <Text size="sm" fw={600} truncate>
                    {user?.full_name}
                  </Text>
                  <Text size="xs" c="dimmed" truncate>
                    {user?.email}
                  </Text>
                  {user?.roles.map((g) => (
                    <Text key={`${g.role}-${g.branch_id}`} size="xs" c="dimmed">
                      {ROLE_LABEL[g.role]}
                      {g.branch_id ? `, ${g.branch_id}` : ""}
                    </Text>
                  ))}
                </Stack>
                <Menu.Divider />
                <Menu.Item leftSection={<IconLogout size={16} stroke={1.6} />} onClick={logout}>
                  Log out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm" aria-label="Main">
        <ScrollArea>
          <Stack gap="lg" pt="xs">
            {NAV.map(({ section, items }) => {
              const visible = items.filter((i) => hasRole(user, i.roles));
              if (visible.length === 0) return null;
              return (
                <div key={section}>
                  <p className="nav-section">{section}</p>
                  <Stack gap={2}>
                    {visible.map(({ to, label, icon: ItemIcon }) => (
                      <NavLink
                        key={to}
                        component={RouterLink}
                        to={to}
                        end
                        label={label}
                        leftSection={<ItemIcon size={18} stroke={1.6} />}
                        active={location.pathname === to}
                        classNames={{ root: "nav-item" }}
                        onClick={close}
                      />
                    ))}
                  </Stack>
                </div>
              );
            })}
          </Stack>
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main id="main">
        <div className="page">
          <Outlet />
        </div>
      </AppShell.Main>
    </AppShell>
  );
}
