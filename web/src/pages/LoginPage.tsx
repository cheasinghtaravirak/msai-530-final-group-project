import { Alert, Avatar, Button, Card, Center, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { IconBuildingStore } from "@tabler/icons-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { homePath } from "../auth/roles";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePath(user)} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email, password);
      navigate(homePath(u), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Center className="login-canvas" p="md">
      <Stack w="100%" maw={380} gap="lg">
        <Stack align="center" gap="sm">
          <Avatar radius="lg" size={52} color="accent" variant="filled" aria-hidden>
            <IconBuildingStore size={30} stroke={1.6} />
          </Avatar>
          <Stack align="center" gap={2}>
            <Title order={1}>Retail Ops</Title>
            <Text c="dimmed">Sign in with your staff account</Text>
          </Stack>
        </Stack>
        <Card padding="xl">
          <form onSubmit={onSubmit}>
            <Stack gap="md">
              {error && (
                <Alert color="red" radius="md">
                  {error}
                </Alert>
              )}
              <TextInput
                label="Email"
                type="email"
                autoComplete="username"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
              <PasswordInput
                label="Password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
              <Button type="submit" size="md" loading={busy} fullWidth mt="xs">
                Sign in
              </Button>
            </Stack>
          </form>
        </Card>
      </Stack>
    </Center>
  );
}
