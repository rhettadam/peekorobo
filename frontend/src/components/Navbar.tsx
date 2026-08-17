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
  IconPencil,
  IconStar,
  IconSun,
  IconUser,
} from "@tabler/icons-react";
import { useState, forwardRef, type CSSProperties, type ReactNode } from "react";
import { NavLink, Link, useLocation, useNavigate } from "react-router-dom";
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

const GAME_LINKS = [
  { to: "/games/higher-lower", label: "Higher or Lower" },
  { to: "/games/duel", label: "Duel" },
  { to: "/games/predictor", label: "Match Predictor" },
];

const MOBILE_LINKS = [...LINKS, { to: "/compare", label: "Compare" }];

const API_DOCS_URL = `${API_BASE}/docs`;

const NAV_TEXT = "#f1f3f5";
const NAV_HOVER = "#ffdd00";

const mobileLinkStyle: CSSProperties = {
  textDecoration: "none",
  color: NAV_TEXT,
  padding: "6px 0",
  fontWeight: 500,
  textAlign: "center",
};

const NavMenuTrigger = forwardRef<HTMLButtonElement, { label: string; active: boolean }>(
  function NavMenuTrigger({ label, active, ...others }, ref) {
    return (
      <UnstyledButton
        {...others}
        ref={ref}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontWeight: active ? 700 : 500,
          color: active ? NAV_HOVER : NAV_TEXT,
          padding: "6px 10px",
          borderRadius: 6,
          whiteSpace: "nowrap",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = NAV_HOVER;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = active ? NAV_HOVER : NAV_TEXT;
        }}
      >
        {label}
        <IconChevronDown size={14} />
      </UnstyledButton>
    );
  },
);

function MobileFold({
  label,
  active,
  children,
}: {
  label: string;
  active?: boolean;
  children: ReactNode;
}) {
  const [opened, setOpened] = useState(false);
  return (
    <Stack gap={4} align="center" w="100%">
      <UnstyledButton
        onClick={() => setOpened((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontWeight: active || opened ? 700 : 500,
          color: active || opened ? NAV_HOVER : NAV_TEXT,
          padding: "6px 0",
        }}
      >
        {label}
        <IconChevronDown
          size={14}
          style={{ transform: opened ? "rotate(180deg)" : undefined, transition: "transform 150ms" }}
        />
      </UnstyledButton>
      <Collapse in={opened}>
        <Stack gap="xs" align="center">
          {children}
        </Stack>
      </Collapse>
    </Stack>
  );
}

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
      <Group gap="xs" wrap="nowrap">
        <Button component={Link} to="/login" variant="default" size="sm" onClick={onNavigate}>
          Login
        </Button>
        <Button component={Link} to="/register" size="sm" onClick={onNavigate}>
          Register
        </Button>
      </Group>
    );
  }

  return (
    <Menu shadow="md" width={200} position="bottom-end" trigger="click">
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
        <Menu.Item
          leftSection={<IconUser size={16} />}
          onClick={() => {
            onNavigate();
            navigate("/user");
          }}
        >
          My Profile
        </Menu.Item>
        <Menu.Item
          leftSection={<IconStar size={16} />}
          onClick={() => {
            onNavigate();
            navigate("/user#profile-favorites");
          }}
        >
          Favorites
        </Menu.Item>
        <Menu.Item
          leftSection={<IconPencil size={16} />}
          onClick={() => {
            onNavigate();
            navigate("/user?edit=1");
          }}
        >
          Edit Profile
        </Menu.Item>
        <Divider />
        <Menu.Item
          color="red"
          leftSection={<IconLogout size={16} />}
          onClick={() => {
            logout();
            onNavigate();
            navigate("/");
          }}
        >
          Logout
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function MobileAuthLinks({ onNavigate }: { onNavigate: () => void }) {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  if (!isAuthenticated || !user) {
    return (
      <>
        <NavLink to="/login" onClick={onNavigate} style={mobileLinkStyle}>
          Login
        </NavLink>
        <NavLink to="/register" onClick={onNavigate} style={mobileLinkStyle}>
          Register
        </NavLink>
      </>
    );
  }
  return (
    <MobileFold label="Profile" active={location.pathname.startsWith("/user")}>
      <NavLink to="/user" onClick={onNavigate} style={mobileLinkStyle}>
        My Profile
      </NavLink>
      <NavLink to="/user#profile-favorites" onClick={onNavigate} style={mobileLinkStyle}>
        Favorites
      </NavLink>
      <NavLink to="/user?edit=1" onClick={onNavigate} style={mobileLinkStyle}>
        Edit Profile
      </NavLink>
      <Text
        component="button"
        style={{ ...mobileLinkStyle, background: "none", border: "none", cursor: "pointer" }}
        onClick={() => {
          logout();
          onNavigate();
          navigate("/");
        }}
      >
        Logout
      </Text>
    </MobileFold>
  );
}

interface NavbarProps {
  mobileOpened: boolean;
  onToggleMobile: () => void;
  onNavigate: () => void;
}

export function Navbar({ mobileOpened, onToggleMobile, onNavigate }: NavbarProps) {
  const location = useLocation();
  const gamesActive = location.pathname.startsWith("/games");
  const miscActive = location.pathname.startsWith("/compare");

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
            <Menu shadow="md" width={210} position="bottom-start" trigger="click">
              <Menu.Target>
                <NavMenuTrigger label="Games" active={gamesActive} />
              </Menu.Target>
              <Menu.Dropdown>
                {GAME_LINKS.map((link) => (
                  <Menu.Item key={link.to} component={NavLink} to={link.to} onClick={onNavigate}>
                    {link.label}
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
            <Menu shadow="md" width={210} position="bottom-start" trigger="click">
              <Menu.Target>
                <NavMenuTrigger label="Misc" active={miscActive} />
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
          <Group visibleFrom="md" wrap="nowrap">
            <UserMenu onNavigate={onNavigate} />
          </Group>
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
          <MobileFold label="Games" active={gamesActive}>
            {GAME_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={onNavigate}
                style={({ isActive }) => ({
                  ...mobileLinkStyle,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? NAV_HOVER : NAV_TEXT,
                })}
              >
                {link.label}
              </NavLink>
            ))}
          </MobileFold>
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={onNavigate}
            style={mobileLinkStyle}
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
