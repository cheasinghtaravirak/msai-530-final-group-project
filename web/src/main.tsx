import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "./styles.css";

import { Badge, Card, MantineProvider, Menu, Modal, Table, createTheme, rem } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { BranchProvider } from "./auth/BranchContext";

const SYSTEM_FONT =
  'system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

const theme = createTheme({
  primaryColor: "accent",
  // Shade 6 (#0071e3) keeps white button text above 4.5:1 in both schemes.
  primaryShade: { light: 6, dark: 6 },
  colors: {
    accent: [
      "#e8f2fe",
      "#d0e4fc",
      "#a3cbfa",
      "#6eaef7",
      "#409cff",
      "#1a86f5",
      "#0071e3",
      "#0062c4",
      "#00519f",
      "#003f7a",
    ],
    gray: [
      "#f5f5f7",
      "#ededf0",
      "#e5e5ea",
      "#dcdce0",
      "#d2d2d7",
      "#8e8e93",
      "#6e6e73",
      "#515154",
      "#3a3a3c",
      "#1d1d1f",
    ],
    dark: [
      "#f5f5f7",
      "#d1d1d6",
      "#a1a1a6",
      "#7c7c80",
      "#3a3a3c",
      "#323234",
      "#2c2c2e",
      "#1c1c1e",
      "#161618",
      "#111113",
    ],
  },
  black: "#1d1d1f",
  white: "#ffffff",
  fontFamily: SYSTEM_FONT,
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  fontSizes: { xs: rem(12), sm: rem(13), md: rem(15), lg: rem(17), xl: rem(20) },
  lineHeights: { xs: "1.4", sm: "1.45", md: "1.47", lg: "1.47", xl: "1.4" },
  headings: {
    fontFamily: SYSTEM_FONT,
    fontWeight: "700",
    sizes: {
      h1: { fontSize: rem(28), lineHeight: "1.14" },
      h2: { fontSize: rem(22), lineHeight: "1.18", fontWeight: "600" },
      h3: { fontSize: rem(17), lineHeight: "1.29", fontWeight: "600" },
      h4: { fontSize: rem(15), lineHeight: "1.33", fontWeight: "600" },
    },
  },
  radius: { xs: rem(4), sm: rem(6), md: rem(8), lg: rem(12), xl: rem(16) },
  defaultRadius: "md",
  shadows: {
    xs: "0 1px 2px rgb(16 24 40 / 0.04)",
    sm: "0 1px 2px rgb(16 24 40 / 0.05), 0 1px 3px rgb(16 24 40 / 0.04)",
    md: "0 4px 12px rgb(16 24 40 / 0.08), 0 1px 3px rgb(16 24 40 / 0.05)",
    lg: "0 12px 32px rgb(16 24 40 / 0.12), 0 2px 6px rgb(16 24 40 / 0.06)",
    xl: "0 24px 48px rgb(16 24 40 / 0.16)",
  },
  activeClassName: "press",
  respectReducedMotion: true,
  components: {
    Badge: Badge.extend({
      defaultProps: { variant: "light", radius: "sm", size: "md" },
      styles: { root: { textTransform: "none", fontWeight: 600, letterSpacing: 0, minWidth: "max-content" } },
    }),
    Card: Card.extend({ defaultProps: { radius: "lg", padding: "lg" }, classNames: { root: "surface" } }),
    Menu: Menu.extend({
      defaultProps: { radius: "md", shadow: "lg", transitionProps: { transition: "pop-top-right", duration: 120 } },
    }),
    Modal: Modal.extend({
      defaultProps: { radius: "lg", centered: true, overlayProps: { backgroundOpacity: 0.35 } },
    }),
    Table: Table.extend({ defaultProps: { verticalSpacing: "sm", horizontalSpacing: "md" } }),
  },
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <Notifications position="top-right" />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <BranchProvider>
              <App />
            </BranchProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
