import { useMemo, useState } from "react";
import { Badge, Combobox, Group, Paper, Text, TextInput, useCombobox } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { IconCalendarEvent, IconMapPin, IconSearch } from "@tabler/icons-react";
import type { MapEvent, MapTeam } from "../../types/api";

export type MapSearchResult =
  | { type: "team"; team: MapTeam }
  | { type: "event"; event: MapEvent };

interface MapSearchProps {
  teams: MapTeam[];
  events: MapEvent[];
  onSelect: (result: MapSearchResult) => void;
}

export function MapSearch({ teams, events, onSelect }: MapSearchProps) {
  const [value, setValue] = useState("");
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });
  const isMobile = useMediaQuery("(max-width: 48em)");

  const results = useMemo<MapSearchResult[]>(() => {
    const q = value.trim().toLowerCase();
    if (!q) return [];
    const out: MapSearchResult[] = [];
    for (const t of teams) {
      const num = String(t.team_number);
      const nick = (t.nickname ?? "").toLowerCase();
      if (num.startsWith(q) || num === q || nick.includes(q)) {
        out.push({ type: "team", team: t });
        if (out.length >= 8) break;
      }
    }
    const half = out.length;
    for (const e of events) {
      const name = (e.name ?? "").toLowerCase();
      const key = e.event_key.toLowerCase();
      if (name.includes(q) || key.includes(q)) {
        out.push({ type: "event", event: e });
        if (out.length >= half + 8) break;
      }
    }
    return out.slice(0, 12);
  }, [value, teams, events]);

  function choose(r: MapSearchResult) {
    setValue("");
    combobox.closeDropdown();
    onSelect(r);
  }

  const options = results.map((r, i) => (
    <Combobox.Option
      value={String(i)}
      key={r.type === "team" ? `t${r.team.team_number}` : `e${r.event.event_key}`}
    >
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        {r.type === "team" ? (
          <IconMapPin size={16} style={{ opacity: 0.7, flexShrink: 0 }} />
        ) : (
          <IconCalendarEvent size={16} style={{ opacity: 0.7, flexShrink: 0 }} />
        )}
        <Text size="sm" truncate>
          {r.type === "team"
            ? `${r.team.team_number} | ${r.team.nickname ?? ""}`
            : r.event.name ?? r.event.event_key}
        </Text>
        <Badge size="xs" variant="light" color={r.type === "team" ? "peeko" : "gray"} ml="auto">
          {r.type === "team" ? "Team" : "Event"}
        </Badge>
      </Group>
    </Combobox.Option>
  ));

  return (
    <Paper
      radius="md"
      style={
        isMobile
          ? {
              position: "absolute",
              left: 12,
              right: 12,
              bottom: 12,
              top: "auto",
              zIndex: 5,
              width: "auto",
              maxWidth: "none",
            }
          : {
              position: "absolute",
              top: 12,
              right: 12,
              zIndex: 5,
              width: 240,
              maxWidth: "min(240px, calc(100vw - 28px))",
            }
      }
    >
      <Combobox
        store={combobox}
        onOptionSubmit={(val) => {
          const r = results[Number(val)];
          if (r) choose(r);
        }}
      >
        <Combobox.Target>
          <TextInput
            placeholder="Find a team or event..."
            leftSection={<IconSearch size={16} />}
            size="sm"
            value={value}
            onChange={(e) => {
              setValue(e.currentTarget.value);
              combobox.openDropdown();
              combobox.updateSelectedOptionIndex();
            }}
            onFocus={() => combobox.openDropdown()}
            onBlur={() => combobox.closeDropdown()}
          />
        </Combobox.Target>
        <Combobox.Dropdown hidden={results.length === 0}>
          <Combobox.Options mah={isMobile ? 220 : 320} style={{ overflowY: "auto" }}>
            {options}
          </Combobox.Options>
        </Combobox.Dropdown>
      </Combobox>
    </Paper>
  );
}
