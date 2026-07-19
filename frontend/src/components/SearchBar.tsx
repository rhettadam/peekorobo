import { useMemo, useState } from "react";
import { Badge, Combobox, Group, Text, TextInput, useCombobox } from "@mantine/core";
import { IconCalendarEvent, IconSearch } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import { useSearchIndex } from "../api/queries";
import { searchIndex, type Suggestion } from "../api/search";
import { TeamAvatar } from "./TeamAvatar";
import { CURRENT_YEAR } from "../lib/constants";

interface SearchBarProps {
  onNavigate?: () => void;
  size?: string;
}

function suggestionHref(s: Suggestion): string {
  if (s.type === "team") {
    const year = s.lastYear ?? CURRENT_YEAR;
    return `/team/${s.teamNumber}/${year}`;
  }
  return `/event/${s.eventKey}`;
}

export function SearchBar({ onNavigate, size }: SearchBarProps) {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const { data: index } = useSearchIndex();
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });

  const suggestions = useMemo(() => {
    if (!index || value.trim().length === 0) return [];
    return searchIndex(index, value, 10);
  }, [index, value]);

  function go(s: Suggestion) {
    setValue("");
    combobox.closeDropdown();
    onNavigate?.();
    navigate(suggestionHref(s));
  }

  function handleSubmit() {
    const q = value.trim();
    if (!q) return;
    if (/^\d+$/.test(q)) {
      setValue("");
      combobox.closeDropdown();
      onNavigate?.();
      navigate(`/team/${q}`);
      return;
    }
    if (suggestions.length > 0) go(suggestions[0]);
  }

  const options = suggestions.map((s, i) => (
    <Combobox.Option value={String(i)} key={s.type === "team" ? `t${s.teamNumber}` : `e${s.eventKey}`}>
      <Group justify="space-between" wrap="nowrap" gap="sm">
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          {s.type === "team" ? (
            <TeamAvatar teamNumber={s.teamNumber} size={24} radius={4} bordered />
          ) : (
            <IconCalendarEvent size={20} style={{ opacity: 0.7, flexShrink: 0 }} />
          )}
          <Text size="sm" truncate>
            {s.type === "team" ? `${s.teamNumber} | ${s.nickname}` : s.name}
          </Text>
        </Group>
        {s.type === "team" ? (
          <Badge size="xs" variant="light" color="gray">Team</Badge>
        ) : (
          <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>{s.eventKey}</Text>
        )}
      </Group>
    </Combobox.Option>
  ));

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(val) => {
        const s = suggestions[Number(val)];
        if (s) go(s);
      }}
    >
      <Combobox.Target>
        <TextInput
          size={size}
          placeholder="Search teams or events..."
          leftSection={<IconSearch size={16} />}
          value={value}
          onChange={(e) => {
            setValue(e.currentTarget.value);
            combobox.openDropdown();
            combobox.updateSelectedOptionIndex();
          }}
          onFocus={() => combobox.openDropdown()}
          onBlur={() => combobox.closeDropdown()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
      </Combobox.Target>
      <Combobox.Dropdown hidden={suggestions.length === 0}>
        <Combobox.Options>{options}</Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
