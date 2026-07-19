import { useEffect, useState } from "react";
import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Image,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { BRAND } from "../lib/assets";

export function Login() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = "Login - Peekorobo";
  }, []);

  useEffect(() => {
    if (isAuthenticated) navigate("/user", { replace: true });
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ username: username.trim(), password });
      navigate("/user", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please try again.");
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
            Login
          </Title>

          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          ) : null}

          <form onSubmit={handleSubmit}>
            <Stack gap="sm">
              <TextInput
                label="Username or Email"
                placeholder="Username or Email"
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
                autoFocus
              />
              <PasswordInput
                label="Password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />
              <Button type="submit" fullWidth loading={loading} mt="xs">
                Login
              </Button>
            </Stack>
          </form>

          <Text ta="center" size="sm">
            Don't have an account?{" "}
            <Anchor component={Link} to="/register">
              Register
            </Anchor>
          </Text>
        </Stack>
      </Card>
    </Center>
  );
}
