import { useState } from "react";
import { STOCK_AVATAR, teamAvatar } from "../lib/assets";

interface TeamAvatarProps {
  teamNumber: number | string;
  size?: number;
  radius?: number;
  /** Optional border/background so avatars read well on any surface. */
  bordered?: boolean;
  /**
   * Enhance rendering for large display sizes. Source avatars are only 40x40, so
   * when shown big (e.g. the 150px team-page hero) they look soft. This keeps
   * high-quality smooth scaling and layers a light unsharp-mask + contrast pass
   * to crisp up edges. Intended only for the one large hero avatar per page, not
   * list/table avatars.
   */
  upscale?: boolean;
}

/**
 * Team avatar image with a graceful fallback to the stock avatar for teams that
 * don't have one. Avatars live in assets/avatars/<team>.png.
 */
export function TeamAvatar({
  teamNumber,
  size = 40,
  radius = 8,
  bordered = false,
  upscale = false,
}: TeamAvatarProps) {
  const [errored, setErrored] = useState(false);
  const src = errored ? STOCK_AVATAR : teamAvatar(teamNumber);
  return (
    <>
      {upscale ? (
        // A mild 3x3 sharpen kernel (sums to 1 so brightness is preserved).
        // preserveAlpha avoids dark halos around transparent avatar edges.
        <svg width={0} height={0} style={{ position: "absolute" }} aria-hidden focusable="false">
          <defs>
            <filter
              id="peeko-avatar-sharpen"
              x="-10%"
              y="-10%"
              width="120%"
              height="120%"
              colorInterpolationFilters="sRGB"
            >
              <feConvolveMatrix
                order="3"
                preserveAlpha="true"
                kernelMatrix="0 -0.55 0 -0.55 3.2 -0.55 0 -0.55 0"
              />
            </filter>
          </defs>
        </svg>
      ) : null}
      <img
        src={src}
        alt={`Team ${teamNumber} avatar`}
        width={size}
        height={size}
        loading="lazy"
        onError={() => setErrored(true)}
        style={{
          width: size,
          height: size,
          objectFit: "contain",
          borderRadius: radius,
          background: bordered ? "rgba(255,255,255,0.06)" : undefined,
          border: bordered ? "1px solid var(--mantine-color-default-border)" : undefined,
          flexShrink: 0,
          imageRendering: upscale ? "auto" : undefined,
          filter: upscale
            ? "url(#peeko-avatar-sharpen) contrast(1.06) saturate(1.08)"
            : undefined,
        }}
      />
    </>
  );
}
