import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActionIcon,
  Alert,
  Button,
  Card,
  Code,
  ColorInput,
  CopyButton,
  Grid,
  Group,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconAlertCircle,
  IconCheck,
  IconCopy,
  IconKey,
  IconLogout,
  IconRefresh,
  IconTrash,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useFavorites, useToggleFavorite } from "../api/favorites";
import { fetchApiKey, generateApiKey, revokeApiKey, updateProfile } from "../api/auth";
import { ApiError } from "../api/client";
import { AvatarPicker } from "../components/AvatarPicker";
import { LoadingState, EmptyState } from "../components/StateWrappers";
import { UserListModal } from "../components/UserListModal";
import {
  CommunityCard,
  FavoriteEventCard,
  FavoriteTeamCard,
  FavoritesSectionHeader,
  ProfileHero,
} from "../components/ProfileSections";
import type { ApiKeyResponse, UpdateProfilePayload } from "../types/api";

function FavoriteTeamsCard() {
  const { data, isLoading } = useFavorites();
  const toggle = useToggleFavorite();
  const teams = (data?.teams ?? []).slice().sort((a, b) => Number(a) - Number(b));
  return (
    <Card withBorder radius="md" p="md">
      <FavoritesSectionHeader label="Favorite Teams" count={teams.length} />
      {isLoading ? (
        <Text size="sm" c="dimmed">
          Loading...
        </Text>
      ) : teams.length === 0 ? (
        <EmptyState>No favorite teams yet. Star a team to see it here.</EmptyState>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          {teams.map((t) => (
            <FavoriteTeamCard
              key={t}
              teamNumber={t}
              onRemove={() => toggle.mutate({ itemType: "team", itemKey: t, favorited: true })}
            />
          ))}
        </SimpleGrid>
      )}
    </Card>
  );
}

function FavoriteEventsCard() {
  const { data, isLoading } = useFavorites();
  const toggle = useToggleFavorite();
  const events = (data?.events ?? []).slice().sort();
  return (
    <Card withBorder radius="md" p="md">
      <FavoritesSectionHeader label="Favorite Events" count={events.length} />
      {isLoading ? (
        <Text size="sm" c="dimmed">
          Loading...
        </Text>
      ) : events.length === 0 ? (
        <EmptyState>No favorite events yet. Star an event to see it here.</EmptyState>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          {events.map((e) => (
            <FavoriteEventCard
              key={e}
              eventKey={e}
              onRemove={() => toggle.mutate({ itemType: "event", itemKey: e, favorited: true })}
            />
          ))}
        </SimpleGrid>
      )}
    </Card>
  );
}

function ApiKeySection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["api-key"],
    queryFn: fetchApiKey,
    staleTime: 60 * 1000,
  });
  const [revealed, setRevealed] = useState(false);

  const setKeyData = (res: ApiKeyResponse) => queryClient.setQueryData(["api-key"], res);

  const generate = useMutation({
    mutationFn: generateApiKey,
    onSuccess: (res) => {
      setKeyData(res);
      setRevealed(true);
      notifications.show({ title: "API key ready", message: "Your API key has been generated.", color: "green" });
    },
    onError: (err) =>
      notifications.show({
        title: "Error",
        message: err instanceof Error ? err.message : "Could not generate key.",
        color: "red",
      }),
  });

  const revoke = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: (res) => {
      setKeyData(res);
      setRevealed(false);
      notifications.show({ title: "API key revoked", message: "Your API key has been revoked.", color: "yellow" });
    },
    onError: (err) =>
      notifications.show({
        title: "Error",
        message: err instanceof Error ? err.message : "Could not revoke key.",
        color: "red",
      }),
  });

  const apiKey = data?.api_key ?? null;
  const masked = apiKey ? "•".repeat(Math.min(apiKey.length, 43)) : "";

  return (
    <Card withBorder radius="lg" p="lg">
      <Group gap={8} mb="xs">
        <IconKey size={18} />
        <Title order={4}>Developer API Key</Title>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        Use this key in the <Code>X-API-Key</Code> header to get a dedicated rate-limit bucket on the
        Peekorobo API. Keep it secret; anyone with the key can use it as you.
      </Text>

      {isLoading ? (
        <Text size="sm" c="dimmed">
          Loading...
        </Text>
      ) : apiKey ? (
        <Stack gap="sm">
          <Group gap="xs" wrap="nowrap">
            <Code style={{ flex: 1, overflowX: "auto", padding: "8px 10px" }}>
              {revealed ? apiKey : masked}
            </Code>
            <Button variant="default" size="xs" onClick={() => setRevealed((v) => !v)}>
              {revealed ? "Hide" : "Show"}
            </Button>
            <CopyButton value={apiKey} timeout={1500}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? "Copied" : "Copy"} withArrow>
                  <ActionIcon variant="default" size="lg" aria-label="Copy API key" onClick={copy}>
                    {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  </ActionIcon>
                </Tooltip>
              )}
            </CopyButton>
          </Group>
          <Group gap="sm">
            <Button
              variant="light"
              size="xs"
              leftSection={<IconRefresh size={14} />}
              loading={generate.isPending}
              onClick={() => generate.mutate()}
            >
              Regenerate
            </Button>
            <Button
              variant="light"
              color="red"
              size="xs"
              leftSection={<IconTrash size={14} />}
              loading={revoke.isPending}
              onClick={() => revoke.mutate()}
            >
              Revoke
            </Button>
          </Group>
        </Stack>
      ) : (
        <Button
          leftSection={<IconKey size={16} />}
          loading={generate.isPending}
          onClick={() => generate.mutate()}
        >
          Generate API Key
        </Button>
      )}
    </Card>
  );
}

export function Profile() {
  const navigate = useNavigate();
  const { user, isLoading, isAuthenticated, logout, setUser } = useAuth();
  const { data: favorites } = useFavorites();

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listMode, setListMode] = useState<"followers" | "following" | null>(null);

  // Edit form fields
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("");
  const [team, setTeam] = useState("");
  const [bio, setBio] = useState("");
  const [avatarKey, setAvatarKey] = useState("");
  const [color, setColor] = useState("");

  useEffect(() => {
    document.title = "My Profile - Peekorobo";
  }, []);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate("/login", { replace: true });
  }, [isLoading, isAuthenticated, navigate]);

  useEffect(() => {
    if (user) {
      setUsername(user.username);
      setEmail(user.email ?? "");
      setRole(user.role ?? "");
      setTeam(user.team ?? "");
      setBio(user.bio ?? "");
      setAvatarKey(user.avatar_key ?? "stock");
      setColor(user.color ?? "");
    }
  }, [user]);

  if (isLoading) return <LoadingState label="Loading your profile..." />;
  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    const payload: UpdateProfilePayload = {
      username: username.trim(),
      email: email.trim(),
      role: role.trim(),
      team: team.trim(),
      bio,
      avatar_key: avatarKey.trim() || "stock",
      color: color || undefined,
    };
    if (password.trim()) payload.password = password.trim();
    try {
      const updated = await updateProfile(payload);
      setUser(updated);
      setPassword("");
      setEditing(false);
      notifications.show({ title: "Saved", message: "Profile updated.", color: "green" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save profile.");
    } finally {
      setSaving(false);
    }
  };

  const favoritesCount = (favorites?.teams.length ?? 0) + (favorites?.events.length ?? 0);

  return (
    <Stack gap="lg" py="md">
      <ProfileHero
        user={user}
        favoritesCount={favoritesCount}
        onShowFollowers={() => setListMode("followers")}
        onShowFollowing={() => setListMode("following")}
        actions={
          <>
            <Button variant="white" color="dark" size="sm" onClick={() => setEditing((v) => !v)}>
              {editing ? "Cancel" : "Edit Profile"}
            </Button>
            <Button
              variant="light"
              color="red"
              size="sm"
              leftSection={<IconLogout size={16} />}
              onClick={handleLogout}
            >
              Logout
            </Button>
          </>
        }
      />

      {listMode ? (
        <UserListModal
          username={user.username}
          mode={listMode}
          opened={listMode !== null}
          onClose={() => setListMode(null)}
        />
      ) : null}

      {editing ? (
        <Card withBorder radius="lg" p="lg">
          <Title order={4} mb="md">
            Edit Profile
          </Title>
          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />} mb="md">
              {error}
            </Alert>
          ) : null}
          <Grid>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput label="Username" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput label="Email" value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput label="Role" placeholder="e.g. Student, Mentor, Fan" value={role} onChange={(e) => setRole(e.currentTarget.value)} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput label="Team" placeholder="e.g. 254" value={team} onChange={(e) => setTeam(e.currentTarget.value)} />
            </Grid.Col>
            <Grid.Col span={12}>
              <Textarea label="Bio" autosize minRows={2} maxRows={6} value={bio} onChange={(e) => setBio(e.currentTarget.value)} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <PasswordInput
                label="New Password"
                placeholder="Leave blank to keep current"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <ColorInput label="Profile Accent Color" format="hex" value={color} onChange={setColor} />
            </Grid.Col>
            <Grid.Col span={12}>
              <AvatarPicker value={avatarKey} onChange={setAvatarKey} suggestTeam={team.trim() || undefined} />
            </Grid.Col>
          </Grid>
          <Group mt="lg" justify="flex-end">
            <Button variant="default" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button loading={saving} onClick={handleSave}>
              Save Changes
            </Button>
          </Group>
        </Card>
      ) : null}

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <FavoriteTeamsCard />
        <FavoriteEventsCard />
      </SimpleGrid>

      <CommunityCard username={user.username} onOpen={(mode) => setListMode(mode)} />

      <ApiKeySection />
    </Stack>
  );
}
