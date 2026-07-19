import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Image,
  List,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconCheck, IconX } from "@tabler/icons-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { BRAND } from "../lib/assets";

interface Rule {
  label: string;
  ok: boolean;
}

export function Register() {
  const navigate = useNavigate();
  const { register, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = "Register - Peekorobo";
  }, []);

  useEffect(() => {
    if (isAuthenticated) navigate("/user", { replace: true });
  }, [isAuthenticated, navigate]);

  const rules = useMemo<Rule[]>(
    () => [
      { label: "At least 8 characters", ok: password.length >= 8 },
      { label: "An uppercase letter", ok: /[A-Z]/.test(password) },
      { label: "A lowercase letter", ok: /[a-z]/.test(password) },
      { label: "A number", ok: /[0-9]/.test(password) },
    ],
    [password],
  );

  const passwordValid = rules.every((r) => r.ok);
  const canSubmit = username.trim().length >= 3 && passwordValid && password === confirm;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (username.trim().length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (!passwordValid) {
      setError("Password does not meet the requirements.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await register({
        username: username.trim(),
        password,
        email: email.trim() ? email.trim() : null,
      });
      navigate("/user", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Center py="xl">
      <Card withBorder radius="lg" p="xl" w="100%" maw={440}>
        <Stack gap="md">
          <Center>
            <Image src={BRAND.home} alt="Peekorobo" maw={260} />
          </Center>
          <Title order={2} ta="center">
            Register
          </Title>

          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          ) : null}

          <form onSubmit={handleSubmit}>
            <Stack gap="sm">
              <TextInput
                label="Username"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
                autoFocus
              />
              <TextInput
                label="Email (optional)"
                placeholder="you@example.com"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
              <PasswordInput
                label="Password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />
              {password ? (
                <List spacing={2} size="xs" center>
                  {rules.map((r) => (
                    <List.Item
                      key={r.label}
                      icon={
                        r.ok ? (
                          <IconCheck size={14} color="var(--mantine-color-green-6)" />
                        ) : (
                          <IconX size={14} color="var(--mantine-color-red-6)" />
                        )
                      }
                    >
                      <Text size="xs" c={r.ok ? "green" : "dimmed"}>
                        {r.label}
                      </Text>
                    </List.Item>
                  ))}
                </List>
              ) : null}
              <PasswordInput
                label="Confirm password"
                placeholder="Confirm password"
                value={confirm}
                onChange={(e) => setConfirm(e.currentTarget.value)}
                error={confirm && confirm !== password ? "Passwords do not match" : undefined}
                required
              />
              <Button type="submit" fullWidth loading={loading} disabled={!canSubmit} mt="xs">
                Register
              </Button>
            </Stack>
          </form>

          <Text ta="center" size="sm">
            Already have an account?{" "}
            <Anchor component={Link} to="/login">
              Login
            </Anchor>
          </Text>
        </Stack>
      </Card>
    </Center>
  );
}
