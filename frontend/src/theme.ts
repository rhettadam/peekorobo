import {
  ActionIcon,
  Anchor,
  Button,
  createTheme,
  type CSSVariablesResolver,
  type MantineColorsTuple,
} from "@mantine/core";

// Peekorobo's signature accent is a bright gold/yellow (#ffdd00, see
// assets/css/00-variables.css --navbar-hover). Mantine needs a 10-shade tuple;
// shade 6 is the brand color used for primary buttons/links.
const peeko: MantineColorsTuple = [
  "#fffde7",
  "#fff9c4",
  "#fff59d",
  "#fff176",
  "#ffee58",
  "#ffe93b",
  "#ffdd00",
  "#fbc02d",
  "#f9a825",
  "#f57f17",
];

function isPeekoFilled(
  color: string | undefined,
  variant: string | undefined,
  primaryColor: string,
): boolean {
  return (variant ?? "filled") === "filled" && (color ?? primaryColor) === "peeko";
}

/** Warm off-white surfaces in light mode; semantic tokens for chrome, links, and buttons. */
export const peekoCssVariablesResolver: CSSVariablesResolver = (theme) => ({
  variables: {
    "--peeko-link": theme.colors.peeko[6],
    "--peeko-link-hover": theme.colors.peeko[4],
    "--peeko-chrome-bg": "#1a1a1a",
    "--peeko-chrome-border": "#2b2b2b",
    "--btn-secondary-text": "var(--mantine-color-text)",
    "--btn-secondary-bg": "linear-gradient(180deg, #303030 0%, #242424 100%)",
    "--btn-secondary-bg-hover": "linear-gradient(180deg, #363636 0%, #282828 100%)",
    "--btn-secondary-bg-active": "linear-gradient(180deg, #282828 0%, #1f1f1f 100%)",
    "--btn-secondary-border": "rgba(255, 255, 255, 0.12)",
    "--btn-secondary-border-hover": "rgba(255, 255, 255, 0.16)",
    "--btn-secondary-shadow":
      "inset 0 1px 0 rgba(255, 255, 255, 0.07), 0 1px 3px rgba(0, 0, 0, 0.34)",
    "--btn-secondary-shadow-hover":
      "inset 0 1px 0 rgba(255, 255, 255, 0.09), 0 2px 6px rgba(0, 0, 0, 0.36)",
    "--btn-secondary-shadow-active":
      "inset 0 2px 4px rgba(0, 0, 0, 0.28), 0 1px 1px rgba(0, 0, 0, 0.18)",
    "--btn-tint-base": "#242424",
  },
  light: {
    "--mantine-color-body": "#f3f2ed",
    "--mantine-color-text": "#1a1a1a",
    "--mantine-color-dimmed": "#5f5e5a",
    "--mantine-color-default": "#faf9f6",
    "--mantine-color-default-hover": "#efeee8",
    "--mantine-color-default-border": "#d8d6cf",
    "--mantine-color-default-color": "#1a1a1a",
    "--peeko-link": "#7a5a00",
    "--peeko-link-hover": "#5c4400",
    "--btn-secondary-text": "#1a1a1a",
    "--btn-secondary-bg": "linear-gradient(180deg, #ffffff 0%, #eceae3 100%)",
    "--btn-secondary-bg-hover": "linear-gradient(180deg, #ffffff 0%, #e3e1da 100%)",
    "--btn-secondary-bg-active": "linear-gradient(180deg, #e3e1da 0%, #d8d6cf 100%)",
    "--btn-secondary-border": "rgba(0, 0, 0, 0.12)",
    "--btn-secondary-border-hover": "rgba(0, 0, 0, 0.16)",
    "--btn-secondary-shadow":
      "inset 0 1px 0 rgba(255, 255, 255, 0.95), 0 1px 2px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0, 0, 0, 0.06)",
    "--btn-secondary-shadow-hover":
      "inset 0 1px 0 rgba(255, 255, 255, 1), 0 2px 4px rgba(0, 0, 0, 0.1), 0 4px 12px rgba(0, 0, 0, 0.08)",
    "--btn-secondary-shadow-active":
      "inset 0 2px 4px rgba(0, 0, 0, 0.1), 0 1px 1px rgba(0, 0, 0, 0.06)",
    "--btn-tint-base": "#eceae3",
  },
  dark: {
    "--mantine-color-body": "#1e1e1e",
    "--mantine-color-default": "#262626",
    "--mantine-color-default-hover": "#2c2c2c",
    "--mantine-color-default-border": "#363636",
    "--mantine-color-dimmed": "#a8a8a8",
    "--peeko-link": theme.colors.peeko[6],
    "--peeko-link-hover": theme.colors.peeko[4],
  },
});

export const theme = createTheme({
  primaryColor: "peeko",
  colors: { peeko },
  primaryShade: { light: 6, dark: 6 },
  autoContrast: true,
  luminanceThreshold: 0.4,
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  headings: { fontWeight: "700" },
  defaultRadius: "md",
  components: {
    // Button hierarchy: filled (peeko) = primary CTA; default = secondary (Events-style).
    // CSS also maps subtle/transparent → default. Use light only for tinted actions (e.g. red logout).
    Anchor: Anchor.extend({
      styles: {
        root: {
          color: "var(--peeko-link)",
          "&:hover": {
            color: "var(--peeko-link-hover)",
          },
        },
      },
    }),
    Button: Button.extend({
      defaultProps: {
        radius: "md",
      },
      classNames: (theme, { color, variant }) => ({
        root: isPeekoFilled(color, variant, theme.primaryColor) ? "peeko-tactile-btn" : "",
      }),
      styles: {
        root: {
          fontWeight: 600,
          letterSpacing: "0.01em",
        },
      },
    }),
    ActionIcon: ActionIcon.extend({
      defaultProps: {
        radius: "md",
      },
      classNames: (theme, { color, variant }) => ({
        root: isPeekoFilled(color, variant, theme.primaryColor) ? "peeko-tactile-btn" : "",
      }),
      styles: {
        root: {
          transition: "transform 120ms ease, box-shadow 120ms ease, filter 120ms ease",
        },
      },
    }),
  },
});
