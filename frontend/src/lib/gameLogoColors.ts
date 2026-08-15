import { useEffect, useState } from "react";
import { gameLogo } from "./assets";

export interface LogoColors {
  primary: string;
  secondary: string;
}

const DEFAULT_COLORS: LogoColors = {
  primary: "#6366f1",
  secondary: "#ec4899",
};

const cache = new Map<number, LogoColors>();
const inflight = new Map<number, Promise<LogoColors>>();

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

function parseHex(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return {
    r: parseInt(full.slice(0, 2), 16),
    g: parseInt(full.slice(2, 4), 16),
    b: parseInt(full.slice(4, 6), 16),
  };
}

function colorDistance(a: string, b: string): number {
  const c1 = parseHex(a);
  const c2 = parseHex(b);
  return Math.hypot(c1.r - c2.r, c1.g - c2.g, c1.b - c2.b);
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    img.src = src;
  });
}

/** Sample dominant saturated colors from a game logo PNG. */
async function extractLogoColors(imageUrl: string): Promise<LogoColors> {
  const img = await loadImage(imageUrl);
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return DEFAULT_COLORS;

  ctx.drawImage(img, 0, 0, size, size);
  const { data } = ctx.getImageData(0, 0, size, size);
  const buckets = new Map<string, number>();

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const a = data[i + 3];
    if (a < 128) continue;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const sat = max === 0 ? 0 : (max - min) / max;
    if (lum < 20 || lum > 245 || sat < 0.18) continue;

    const qr = Math.round(r / 16) * 16;
    const qg = Math.round(g / 16) * 16;
    const qb = Math.round(b / 16) * 16;
    const key = rgbToHex(qr, qg, qb);
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }

  const ranked = [...buckets.entries()].sort((a, b) => b[1] - a[1]).map(([hex]) => hex);
  if (ranked.length === 0) return DEFAULT_COLORS;

  const primary = ranked[0];
  const secondary =
    ranked.find((hex) => colorDistance(hex, primary) >= 72) ??
    ranked[1] ??
    primary;

  return { primary, secondary };
}

export async function getGameLogoColors(year: number): Promise<LogoColors> {
  const cached = cache.get(year);
  if (cached) return cached;

  const pending = inflight.get(year);
  if (pending) return pending;

  const promise = extractLogoColors(gameLogo(year))
    .then((colors) => {
      cache.set(year, colors);
      inflight.delete(year);
      return colors;
    })
    .catch(() => {
      inflight.delete(year);
      return DEFAULT_COLORS;
    });

  inflight.set(year, promise);
  return promise;
}

/** Soft banner gradient derived from the season logo's dominant colors. */
export function gameLogoBannerStyle(colors: LogoColors): { background: string; borderColor: string } {
  const primary = parseHex(colors.primary);
  const secondary = parseHex(colors.secondary);
  return {
    background: `linear-gradient(120deg, rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.22) 0%, rgba(${secondary.r}, ${secondary.g}, ${secondary.b}, 0.14) 48%, rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.07) 100%)`,
    borderColor: `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.34)`,
  };
}

export function useGameLogoColors(year: number | null | undefined): LogoColors {
  const [colors, setColors] = useState<LogoColors>(DEFAULT_COLORS);

  useEffect(() => {
    if (!year) {
      setColors(DEFAULT_COLORS);
      return;
    }
    let cancelled = false;
    getGameLogoColors(year).then((next) => {
      if (!cancelled) setColors(next);
    });
    return () => {
      cancelled = true;
    };
  }, [year]);

  return colors;
}
