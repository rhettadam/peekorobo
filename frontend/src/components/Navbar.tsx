import {
  ActionIcon,
  Avatar,
  Burger,
  Button,
  Collapse,
  Divider,
  Group,
  Menu,
  Stack,
  Text,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import {
  IconChevronDown,
  IconLogout,
  IconMoon,
  IconStar,
  IconSun,
  IconUser,
} from "@tabler/icons-react";
import { NavLink, Link, useNavigate } from "react-router-dom";
import { SearchBar } from "./SearchBar";
import { BRAND, userAvatar } from "../lib/assets";
import { API_BASE } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const LINKS = [
  { to: "/teams", label: "Teams" },
  { to: "/events", label: "Events" },
  { to: "/map", label: "Map" },
  { to: "/insights", label: "Insights" },
];

// Secondary items tucked into a "Misc" dropdown to keep the top row short.
const MOBILE_LINKS = [...LINKS, { to: "/compare", label: "Compare" }];

const API_DOCS_URL = `${API_BASE}/docs`;

const NAV_TEXT = "#f1f3f5";
const NAV_HOVER = "#ffdd00";

function ColorSchemeToggle({
  visibleFrom,
  withLabel = false,
}: {
  visibleFrom?: string;
  withLabel?: boolean;
}) {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme("light", { getInitialValueInEffect: true });
  const isDark = computed === "dark";
  const toggle = () => setColorScheme(isDark ? "light" : "dark");

  if (withLabel) {
    return (
      <UnstyledButton
        onClick={toggle}
        aria-label="Toggle color scheme"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          color: NAV_TEXT,
          padding: "6px 0",
          fontWeight: 500,
        }}
      >
        {isDark ? <IconSun size={18} /> : <IconMoon size={18} />}
        {isDark ? "Light mode" : "Dark mode"}
      </UnstyledButton>
    );
  }

  return (
    <ActionIcon
      variant="default"
      size="lg"
      aria-label="Toggle color scheme"
      visibleFrom={visibleFrom}
      onClick={toggle}
    >
      {isDark ? <IconSun size={18} /> : <IconMoon size={18} />}
    </ActionIcon>
  );
}

function UserMenu({ onNavigate }: { onNavigate: () => void }) {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  if (!isAuthenticated || !user) {
    return (
      <Group gap="xs" wrap="nowrap" visibleFrom="md">
        <Button component={Link} to="/login" variant="subtle" color="gray" size="sm" onClick={onNavigate}>
          Login
        </Button>
        <Button component={Link} to="/register" size="sm" onClick={onNavigate}>
          Register
        </Button>
      </Group>
    );
  }

  return (
    <Menu shadow="md" width={200} position="bottom-end">
      <Menu.Target>
        <ActionIcon variant="subtle" size="lg" radius="xl" aria-label="Account menu">
          <Avatar src={userAvatar(user.avatar_key)} size={30} radius="xl" alt={user.username}>
            {user.username.slice(0, 2).toUpperCase()}
          </Avatar>
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          <Text size="xs" truncate>
            {user.username}
          </Text>
        </Menu.Label>
        <Menu.Item leftSection={<IconUser size={16} />} onClick={() => navigate("/user")}>
          My Profile
        </Menu.Item>
        <Menu.Item leftSection={<IconStar size={16} />} onClick={() => navigate("/user")}>
          Favorites
        </Menu.Item>
        <Divider />
        <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={() => {
          logout();
          navigate("/");
        }}>
          Logout
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function MobileAuthLinks({ onNavigate }: { onNavigate: () => void }) {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const linkStyle = { textDecoration: "none", color: NAV_TEXT, padding: "6px 0", fontWeight: 500, textAlign: "center" as const };
  if (!isAuthenticated || !user) {
    return (
      <>
        <NavLink to="/login" onClick={onNavigate} style={linkStyle}>
          Login
        </NavLink>
        <NavLink to="/register" onClick={onNavigate} style={linkStyle}>
          Register
        </NavLink>
      </>
    );
  }
  return (
    <>
      <NavLink to="/user" onClick={onNavigate} style={linkStyle}>
        My Profile
      </NavLink>
      <Text
        component="button"
        style={{ ...linkStyle, background: "none", border: "none", cursor: "pointer" }}
        onClick={() => {
          logout();
          onNavigate();
          navigate("/");
        }}
      >
        Logout
      </Text>
    </>
  );
}

interface NavbarProps {
  mobileOpened: boolean;
  onToggleMobile: () => void;
  onNavigate: () => void;
}

export function Navbar({ mobileOpened, onToggleMobile, onNavigate }: NavbarProps) {
  return (
    <div style={{ height: "100%" }}>
      <Group h="100%" px="md" justify="space-between" wrap="nowrap">
        <Group gap="lg" wrap="nowrap">
          <Link
            to="/"
            onClick={onNavigate}
            style={{ display: "flex", alignItems: "center", height: "100%" }}
          >
            <img
              src={BRAND.logo}
              alt="Peekorobo"
              height={44}
              style={{ display: "block", height: 44, width: "auto" }}
            />
          </Link>
          <Group gap={2} wrap="nowrap" visibleFrom="md">
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={onNavigate}
                style={({ isActive }) => ({
                  textDecoration: "none",
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? NAV_HOVER : NAV_TEXT,
                  padding: "6px 10px",
                  borderRadius: 6,
                  whiteSpace: "nowrap",
                })}
                onMouseEnter={(e) => (e.currentTarget.style.color = NAV_HOVER)}
                onMouseLeave={(e) => {
                  if (!e.currentTarget.classList.contains("active")) e.currentTarget.style.color = NAV_TEXT;
                }}
              >
                {link.label}
              </NavLink>
            ))}
            <Menu shadow="md" width={180} position="bottom-start" trigger="hover" openDelay={0} closeDelay={120}>
              <Menu.Target>
                <UnstyledButton
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontWeight: 500,
                    color: NAV_TEXT,
                    padding: "6px 10px",
                    borderRadius: 6,
                    whiteSpace: "nowrap",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = NAV_HOVER)}
                  onMouseLeave={(e) => (e.currentTarget.style.color = NAV_TEXT)}
                >
                  Misc
                  <IconChevronDown size={14} />
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item component={NavLink} to="/compare" onClick={onNavigate}>
                  Compare
                </Menu.Item>
                <Menu.Item
                  component="a"
                  href={API_DOCS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={onNavigate}
                >
                  API Docs
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>

        <Group gap="sm" wrap="nowrap">
          <div style={{ width: 260, maxWidth: "40vw" }} className="nav-search">
            <SearchBar onNavigate={onNavigate} />
          </div>
          <ColorSchemeToggle visibleFrom="md" />
          <UserMenu onNavigate={onNavigate} />
          <Burger opened={mobileOpened} onClick={onToggleMobile} hiddenFrom="md" size="sm" />
        </Group>
      </Group>

      <Collapse in={mobileOpened} hiddenFrom="md">
        <Stack
          gap="xs"
          px="md"
          py="md"
          align="center"
          style={{
            background: "rgba(17, 17, 17, 0.72)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          }}
        >
          {MOBILE_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={onNavigate}
              style={({ isActive }) => ({
                textDecoration: "none",
                fontWeight: isActive ? 700 : 500,
                color: isActive ? NAV_HOVER : NAV_TEXT,
                padding: "6px 0",
                textAlign: "center",
              })}
            >
              {link.label}
            </NavLink>
          ))}
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={onNavigate}
            style={{ textDecoration: "none", color: NAV_TEXT, padding: "6px 0", fontWeight: 500, textAlign: "center" }}
          >
            API Docs
          </a>
          <Divider my={4} w="100%" />
          <ColorSchemeToggle withLabel />
          <MobileAuthLinks onNavigate={onNavigate} />
        </Stack>
      </Collapse>
    </div>
  );
}
