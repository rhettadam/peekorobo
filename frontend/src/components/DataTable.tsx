import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { Button, Card, Group, Menu, Pagination, Select, Stack, Table, Text } from "@mantine/core";
import {
  IconChevronDown,
  IconChevronUp,
  IconDownload,
  IconFileTypeCsv,
  IconJson,
  IconSelector,
} from "@tabler/icons-react";

export interface Column<T> {
  /** Stable column id. */
  key: string;
  header: ReactNode;
  /** Cell renderer. `index` is the absolute (post-sort) row index, 0-based. */
  render: (row: T, index: number) => ReactNode;
  /** Provide to make the column sortable. */
  sortValue?: (row: T) => number | string | null | undefined;
  width?: number | string;
  align?: "left" | "center" | "right";
  /** Optional per-cell style (e.g. alliance tints, prediction colors). */
  cellStyle?: (row: T) => CSSProperties | undefined;
  /**
   * Plain value used for CSV / JSON export. Falls back to `sortValue` when
   * omitted. Set to `null` to exclude this column from exports (useful for
   * avatar / icon-only columns).
   */
  exportValue?: ((row: T) => number | string | null | undefined) | null;
}

type SortDir = "asc" | "desc";

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  getRowKey: (row: T, index: number) => string | number;
  initialSort?: { key: string; dir: SortDir };
  defaultPageSize?: number;
  pageSizeOptions?: number[];
  minWidth?: number;
  stickyHeader?: boolean;
  rowStyle?: (row: T) => CSSProperties | undefined;
  /** Fired on user-driven sort / page / page-size changes (not initial render). */
  onInteract?: () => void;
  /** Base name for exported files (no extension). Defaults to "peekorobo-export". */
  exportFileName?: string;
  /** Hide the CSV / JSON export control. */
  disableExport?: boolean;
}

const DEFAULT_PAGE_SIZES = [10, 25, 50, 100];

/** Columns that can contribute a plain value to CSV/JSON exports. */
function exportableColumns<T>(columns: Column<T>[]) {
  return columns.filter((c) => c.exportValue !== null && (c.exportValue || c.sortValue));
}

function columnExportValue<T>(col: Column<T>, row: T): number | string | null | undefined {
  if (col.exportValue) return col.exportValue(row);
  return col.sortValue?.(row);
}

function columnHeaderLabel<T>(col: Column<T>): string {
  return typeof col.header === "string" ? col.header : col.key;
}

function csvCell(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function triggerDownload(filename: string, contents: string, mime: string) {
  const blob = new Blob([contents], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function compare(
  a: number | string | null | undefined,
  b: number | string | null | undefined,
): number {
  const an = a === null || a === undefined || (typeof a === "number" && Number.isNaN(a));
  const bn = b === null || b === undefined || (typeof b === "number" && Number.isNaN(b));
  if (an && bn) return 0;
  if (an) return 1; // nulls always last
  if (bn) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/**
 * Generic table with click-to-sort column headers, a rows-per-page selector,
 * and pagination. Cells are rendered via per-column callbacks so complex content
 * (avatars, colored pills, links) still works.
 */
export function DataTable<T>({
  data,
  columns,
  getRowKey,
  initialSort,
  defaultPageSize = 25,
  pageSizeOptions = DEFAULT_PAGE_SIZES,
  minWidth = 600,
  stickyHeader = false,
  rowStyle,
  onInteract,
  exportFileName = "peekorobo-export",
  disableExport = false,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(initialSort?.key ?? null);
  const [sortDir, setSortDir] = useState<SortDir>(initialSort?.dir ?? "desc");
  const [pageSize, setPageSize] = useState<number>(defaultPageSize);
  const [page, setPage] = useState(1);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return data;
    const getVal = col.sortValue;
    const factor = sortDir === "asc" ? 1 : -1;
    return [...data].sort((a, b) => factor * compare(getVal(a), getVal(b)));
  }, [data, columns, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  useEffect(() => {
    if (page > totalPages) setPage(1);
  }, [page, totalPages]);

  const start = (page - 1) * pageSize;
  const pageRows = sorted.slice(start, start + pageSize);

  const toggleSort = (col: Column<T>) => {
    if (!col.sortValue) return;
    onInteract?.();
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      // Numbers usually most-useful high-to-low; text low-to-high.
      const sample = sorted.find((r) => col.sortValue?.(r) != null);
      const isNum = sample ? typeof col.sortValue?.(sample) === "number" : true;
      setSortDir(isNum ? "desc" : "asc");
    }
    setPage(1);
  };

  const exportCols = useMemo(() => exportableColumns(columns), [columns]);

  const handleExport = (format: "csv" | "json") => {
    if (sorted.length === 0 || exportCols.length === 0) return;
    if (format === "csv") {
      const header = exportCols.map((c) => csvCell(columnHeaderLabel(c))).join(",");
      const lines = sorted.map((row) =>
        exportCols.map((c) => csvCell(columnExportValue(c, row))).join(","),
      );
      triggerDownload(`${exportFileName}.csv`, [header, ...lines].join("\r\n"), "text/csv");
    } else {
      const rows = sorted.map((row) => {
        const obj: Record<string, number | string | null> = {};
        for (const c of exportCols) {
          const v = columnExportValue(c, row);
          obj[columnHeaderLabel(c)] = v === undefined ? null : v;
        }
        return obj;
      });
      triggerDownload(
        `${exportFileName}.json`,
        JSON.stringify(rows, null, 2),
        "application/json",
      );
    }
  };

  return (
    <Stack gap="sm">
      <Card withBorder padding={0} radius="md">
        <Table.ScrollContainer minWidth={minWidth}>
          <Table striped highlightOnHover stickyHeader={stickyHeader}>
            <Table.Thead>
              <Table.Tr>
                {columns.map((col) => {
                  const active = sortKey === col.key;
                  const sortable = Boolean(col.sortValue);
                  return (
                    <Table.Th
                      key={col.key}
                      w={col.width}
                      style={{
                        cursor: sortable ? "pointer" : undefined,
                        whiteSpace: "nowrap",
                        userSelect: "none",
                        textAlign: col.align,
                      }}
                      onClick={() => toggleSort(col)}
                    >
                      <Group gap={4} wrap="nowrap" justify={col.align === "right" ? "flex-end" : col.align === "center" ? "center" : "flex-start"}>
                        <span>{col.header}</span>
                        {sortable ? (
                          active ? (
                            sortDir === "asc" ? (
                              <IconChevronUp size={14} />
                            ) : (
                              <IconChevronDown size={14} />
                            )
                          ) : (
                            <IconSelector size={14} style={{ opacity: 0.4 }} />
                          )
                        ) : null}
                      </Group>
                    </Table.Th>
                  );
                })}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {pageRows.map((row, i) => (
                <Table.Tr key={getRowKey(row, start + i)} style={rowStyle?.(row)}>
                  {columns.map((col) => (
                    <Table.Td
                      key={col.key}
                      style={{ textAlign: col.align, ...col.cellStyle?.(row) }}
                    >
                      {col.render(row, start + i)}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>

      <Group justify="space-between" align="center" wrap="wrap">
        <Group gap="xs" align="center">
          <Text size="sm" c="dimmed">
            Rows per page
          </Text>
          <Select
            size="xs"
            w={80}
            value={String(pageSize)}
            data={pageSizeOptions.map((n) => ({ value: String(n), label: String(n) }))}
            onChange={(v) => {
              if (v) {
                onInteract?.();
                setPageSize(Number(v));
                setPage(1);
              }
            }}
            allowDeselect={false}
          />
          <Text size="sm" c="dimmed">
            {sorted.length === 0
              ? "0"
              : `${start + 1}\u2013${Math.min(start + pageSize, sorted.length)} of ${sorted.length.toLocaleString()}`}
          </Text>
          {!disableExport && exportCols.length > 0 ? (
            <Menu position="top-start" withinPortal shadow="md">
              <Menu.Target>
                <Button
                  size="xs"
                  variant="default"
                  leftSection={<IconDownload size={14} />}
                  disabled={sorted.length === 0}
                >
                  Export
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>
                  Export {sorted.length.toLocaleString()} row{sorted.length === 1 ? "" : "s"}
                </Menu.Label>
                <Menu.Item
                  leftSection={<IconFileTypeCsv size={16} />}
                  onClick={() => handleExport("csv")}
                >
                  CSV
                </Menu.Item>
                <Menu.Item leftSection={<IconJson size={16} />} onClick={() => handleExport("json")}>
                  JSON
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          ) : null}
        </Group>
        {totalPages > 1 ? (
          <Pagination
            total={totalPages}
            value={page}
            onChange={(p) => {
              onInteract?.();
              setPage(p);
            }}
            size="sm"
          />
        ) : null}
      </Group>
    </Stack>
  );
}
