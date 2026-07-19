import type { ReactNode } from "react";
import { Alert, Center, Loader, Stack, Text } from "@mantine/core";
import { IconAlertTriangle, IconInbox } from "@tabler/icons-react";

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <Center mih={200}>
      <Stack align="center" gap="xs">
        <Loader color="peeko" />
        <Text c="dimmed" size="sm">
          {label}
        </Text>
      </Stack>
    </Center>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <Alert color="red" icon={<IconAlertTriangle size={18} />} title="Unable to load data" my="md">
      {message}
    </Alert>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <Center mih={160}>
      <Stack align="center" gap="xs">
        <IconInbox size={28} opacity={0.5} />
        <Text c="dimmed" size="sm">
          {children}
        </Text>
      </Stack>
    </Center>
  );
}

/**
 * Convenience wrapper that renders loading/error/empty/content based on a query.
 */
export function QueryBoundary<T>({
  isLoading,
  error,
  data,
  isEmpty,
  loadingLabel,
  emptyMessage,
  children,
}: {
  isLoading: boolean;
  error: unknown;
  data: T | undefined;
  isEmpty?: (data: T) => boolean;
  loadingLabel?: string;
  emptyMessage?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (isLoading) return <LoadingState label={loadingLabel} />;
  if (error) return <ErrorState error={error} />;
  if (data === undefined || data === null) return <EmptyState>{emptyMessage ?? "No data available."}</EmptyState>;
  if (isEmpty && isEmpty(data)) return <EmptyState>{emptyMessage ?? "No data available."}</EmptyState>;
  return <>{children(data)}</>;
}
