import { Anchor, Container, Group, Text } from "@mantine/core";
import { BRAND } from "../lib/assets";

export function Footer() {
  return (
    // Full-bleed band: negative inline/bottom margins cancel AppShell.Main's
    // padding so the top border and background span the entire app width and sit
    // flush at the bottom. Background matches the header for a cohesive bookend.
    <div
      style={{
        marginTop: "var(--mantine-spacing-lg)",
        marginInline: "calc(var(--app-shell-padding, 16px) * -1)",
        marginBottom: "calc(var(--app-shell-padding, 16px) * -1)",
        borderTop: "1px solid #2b2b2b",
        backgroundColor: "#1a1a1a",
      }}
    >
      <Container size="xl" py="sm" px={{ base: "xs", sm: "md" }}>
        <Group justify="center" gap="sm" wrap="wrap">
          <Text size="sm" c="dimmed">
            Built With
          </Text>
          <Anchor
            size="sm"
            fw={500}
            href="https://www.thebluealliance.com/"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Group gap={6} wrap="nowrap" component="span">
              <img src={BRAND.tba} alt="" height={16} style={{ display: "block" }} />
              The Blue Alliance
            </Group>
          </Anchor>
          <Text size="sm" c="dimmed">
            |
          </Text>
          <Anchor
            size="sm"
            fw={500}
            href="https://github.com/rhettadam/peekorobo"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Group gap={6} wrap="nowrap" component="span">
              <img src={BRAND.github} alt="" height={16} style={{ display: "block" }} />
              GitHub
            </Group>
          </Anchor>
        </Group>
      </Container>
    </div>
  );
}
