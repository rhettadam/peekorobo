import { Anchor, Badge, Button, type ButtonProps } from "@mantine/core";
import { IconBroadcast } from "@tabler/icons-react";
import { BRAND } from "../lib/assets";
import { webcastButtonColor, webcastLink } from "../lib/webcast";

function webcastShortLabel(provider: string): string {
  switch (provider) {
    case "twitch":
      return "Twitch";
    case "youtube":
      return "YouTube";
    case "ustream":
      return "Ustream";
    case "livestream":
      return "Livestream";
    default:
      return "Stream";
  }
}

interface WebcastControlProps {
  webcastType?: string | null;
  webcastChannel?: string | null;
  size?: ButtonProps["size"];
  /** Stop click from bubbling (e.g. when inside a card Link). */
  stopPropagation?: boolean;
}

export function WebcastButton({
  webcastType,
  webcastChannel,
  size = "compact-sm",
  stopPropagation = false,
}: WebcastControlProps) {
  const stream = webcastLink({ type: webcastType, channel: webcastChannel });
  if (!stream) return null;

  return (
    <Button
      component="a"
      href={stream.url}
      target="_blank"
      rel="noopener noreferrer"
      size={size}
      variant="filled"
      color={webcastButtonColor(stream.provider)}
      leftSection={<IconBroadcast size={14} />}
      onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
    >
      {webcastShortLabel(stream.provider)}
    </Button>
  );
}

export function WebcastPill({
  webcastType,
  webcastChannel,
  stopPropagation = false,
}: Omit<WebcastControlProps, "size">) {
  const stream = webcastLink({ type: webcastType, channel: webcastChannel });
  if (!stream) return null;

  return (
    <Badge
      component="a"
      href={stream.url}
      target="_blank"
      rel="noopener noreferrer"
      variant="filled"
      color={webcastButtonColor(stream.provider)}
      size="sm"
      style={{ cursor: "pointer", textDecoration: "none" }}
      onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
    >
      {webcastShortLabel(stream.provider)}
    </Badge>
  );
}

interface EventExternalLinksProps {
  eventKey: string;
  year?: number | null;
  iconHeight?: number;
}

/** TBA + FIRST event page links (mirrors team page external links). */
export function EventExternalLinks({ eventKey, year, iconHeight = 22 }: EventExternalLinksProps) {
  const frcYear = year ?? (eventKey.length >= 4 && /^\d{4}/.test(eventKey) ? Number(eventKey.slice(0, 4)) : null);
  return (
    <>
      <Anchor
        href={`https://www.thebluealliance.com/event/${eventKey}`}
        target="_blank"
        rel="noopener noreferrer"
        title="View on The Blue Alliance"
      >
        <img src={BRAND.tba} alt="The Blue Alliance" height={iconHeight} style={{ display: "block", borderRadius: 4 }} />
      </Anchor>
      {frcYear ? (
        <Anchor
          href={`https://frc-events.firstinspires.org/${frcYear}/event/${eventKey}`}
          target="_blank"
          rel="noopener noreferrer"
          title="View on FRC Events"
        >
          <img src={BRAND.frc} alt="FRC Events" height={iconHeight} style={{ display: "block", borderRadius: 4 }} />
        </Anchor>
      ) : null}
    </>
  );
}
