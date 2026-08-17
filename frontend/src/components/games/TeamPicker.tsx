import { useMemo, useState } from "react";
import { ActionIcon, Combobox, Group, Text, TextInput, useCombobox } from "@mantine/core";
import { IconSearch, IconX } from "@tabler/icons-react";
import { useSearchIndex } from "../../api/queries";
import { searchIndex, type Suggestion } from "../../api/search";
import { TeamAvatar } from "../TeamAvatar";

interface TeamPickerProps {
  label?: string;
  placeholder?: string;
  value: number | null;
  onChange: (teamNumber: number | null) => void;
  exclude?: number[];
  w?: number | string;
}

/** Combobox team search used by Duel (and anywhere a team number is picked). */
export function TeamPicker({
  label = "Team",
  placeholder = "Number or name",
  value,
  onChange,
  exclude = [],
  w = 260,
}: TeamPickerProps) {
  const [query, setQuery] = useState("");
  const { data: index } = useSearchIndex();
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });

  const suggestions = useMemo(() => {
    if (!index || query.trim().length === 0) return [];
    return searchIndex(index, query, 12)
      .filter((s): s is Extract<Suggestion, { type: "team" }> => s.type === "team")
      .filter((s) => !exclude.includes(s.teamNumber))
      .slice(0, 8);
  }, [index, query, exclude]);

  const selectedNick =
    value && index?.teams[String(value)]?.nickname ? index.teams[String(value)].nickname : "";

  function pick(n: number) {
    onChange(n);
    setQuery("");
    combobox.closeDropdown();
  }

  function submitRaw() {
    const q = query.trim();
    if (/^\d+$/.test(q)) {
      pick(Number(q));
    } else if (suggestions[0]?.type === "team") {
      pick(suggestions[0].teamNumber);
    }
  }

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(val) => pick(Number(val))}
      withinPortal
    >
      <Combobox.Target>
        <TextInput
          label={label}
          placeholder={placeholder}
          w={w}
          value={value ? `${value}${selectedNick ? ` | ${selectedNick}` : ""}` : query}
          leftSection={
            value ? <TeamAvatar teamNumber={value} size={20} radius={4} /> : <IconSearch size={16} />
          }
          rightSection={
            value ? (
              <ActionIcon
                size="sm"
                variant="subtle"
                aria-label="Clear team"
                onClick={() => {
                  onChange(null);
                  setQuery("");
                }}
              >
                <IconX size={14} />
              </ActionIcon>
            ) : null
          }
          onChange={(e) => {
            if (value) onChange(null);
            setQuery(e.currentTarget.value);
            combobox.openDropdown();
            combobox.updateSelectedOptionIndex();
          }}
          onClick={() => {
            if (!value) combobox.openDropdown();
          }}
          onFocus={() => {
            if (!value && query) combobox.openDropdown();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submitRaw();
            }
          }}
          readOnly={Boolean(value)}
        />
      </Combobox.Target>
      <Combobox.Dropdown>
        <Combobox.Options>
          {suggestions.length === 0 ? (
            <Combobox.Empty>No teams match</Combobox.Empty>
          ) : (
            suggestions.map((s) => (
              <Combobox.Option value={String(s.teamNumber)} key={s.teamNumber}>
                <Group gap="sm" wrap="nowrap">
                  <TeamAvatar teamNumber={s.teamNumber} size={24} radius={4} bordered />
                  <Text size="sm" truncate>
                    {s.teamNumber} | {s.nickname}
                  </Text>
                </Group>
              </Combobox.Option>
            ))
          )}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
