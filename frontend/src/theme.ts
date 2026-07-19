import { createTheme, type MantineColorsTuple } from "@mantine/core";

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
});
