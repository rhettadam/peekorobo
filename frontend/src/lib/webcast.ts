/** Build a watch URL from TBA-style webcast_type + webcast_channel. */

export interface WebcastInfo {
  type: string | null | undefined;
  channel: string | null | undefined;
}

export interface WebcastLink {
  url: string;
  label: string;
  provider: string;
}

function normalizeType(type: string): string {
  return type.trim().toLowerCase();
}

/**
 * Map TBA webcast fields to an external stream URL.
 * Only the first stored webcast is available (pipeline saves webcasts[0]).
 */
export function webcastLink(info: WebcastInfo): WebcastLink | null {
  const type = info.type ? normalizeType(info.type) : "";
  const channel = (info.channel ?? "").trim();
  if (!channel) return null;

  // Some types store a full URL in channel.
  if (/^https?:\/\//i.test(channel)) {
    return { url: channel, label: "Watch stream", provider: type || "stream" };
  }

  switch (type) {
    case "youtube":
      return {
        url: `https://www.youtube.com/watch?v=${encodeURIComponent(channel)}`,
        label: "Watch on YouTube",
        provider: "youtube",
      };
    case "twitch":
      return {
        url: `https://www.twitch.tv/${encodeURIComponent(channel)}`,
        label: "Watch on Twitch",
        provider: "twitch",
      };
    case "ustream":
      return {
        url: `https://www.ustream.tv/channel/${encodeURIComponent(channel)}`,
        label: "Watch on Ustream",
        provider: "ustream",
      };
    case "livestream":
      return {
        url: `https://livestream.com/${channel.replace(/^\/+/, "")}`,
        label: "Watch on Livestream",
        provider: "livestream",
      };
    case "html5":
    case "iframe":
    case "direct_link":
      return { url: channel, label: "Watch stream", provider: type };
    default:
      // Unknown type with a bare channel — don't guess a host.
      return null;
  }
}
