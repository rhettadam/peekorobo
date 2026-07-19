import { Button, Center, Stack, Text, Title } from "@mantine/core";
import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <Center mih={400}>
      <Stack align="center" gap="sm">
        <Title order={1}>404</Title>
        <Text c="dimmed">This page could not be found.</Text>
        <Button component={Link} to="/" variant="light">
          Back home
        </Button>
      </Stack>
    </Center>
  );
}
