import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box, Loader, Overlay, Stack, Text } from "@mantine/core";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { GeoJSONSource, SkySpecification } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { useMapEvents, useMapTeams } from "../api/queries";
import { ErrorState } from "../components/StateWrappers";
import { MapControls, type LayerState, type Projection } from "../components/map/MapControls";
import { MapSearch, type MapSearchResult } from "../components/map/MapSearch";
import { CURRENT_YEAR } from "../lib/constants";
import type { MapEvent, MapTeam } from "../types/api";
import {
  BASEMAP_FALLBACK,
  BASEMAP_PRIMARY,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  coordKey,
  eventPopupHTML,
  eventStackRowHTML,
  eventTypeColor,
  eventsToGeoJSON,
  spreadByCoords,
  stackPopupHTML,
  stackRadiusForZoom,
  teamPopupHTML,
  teamStackRowHTML,
  teamToPopupProps,
  teamsToGeoJSON,
  type EventFeatureProps,
} from "../lib/map";
import { STOCK_AVATAR, teamAvatar } from "../lib/assets";
import { locationString, eventWeekLabel, formatDateRange } from "../lib/format";

const DISTRICTS_URL = `${(import.meta.env.VITE_SEARCH_BASE_URL ?? "/data").replace(/\/$/, "")}/districts.geojson`;

const INITIAL_LAYERS: LayerState = { teams: true, events: true, heatmap: false, districts: false };

// Cap on simultaneously-mounted avatar DOM markers. Viewport culling keeps the
// live count near what's on screen; the cap guards against low-zoom pile-ups.
const MAX_TEAM_MARKERS = 700;

// Space/atmosphere halo for globe mode; a neutral, halo-free sky for 2D.
const GLOBE_SKY: SkySpecification = {
  "sky-color": "#0a0f24",
  "sky-horizon-blend": 0.7,
  "horizon-color": "#4a5a8f",
  "horizon-fog-blend": 0.6,
  "fog-color": "#0b1226",
  "fog-ground-blend": 0.5,
  "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 0.9, 4, 0.6, 8, 0],
};
const FLAT_SKY: SkySpecification = { "atmosphere-blend": 0 };

function applySky(map: maplibregl.Map, projection: Projection) {
  try {
    map.setSky(projection === "globe" ? GLOBE_SKY : FLAT_SKY);
  } catch {
    // setSky unsupported in this build; ignore.
  }
}

function avatarSizeForZoom(zoom: number): number {
  if (zoom < 4) return 22;
  if (zoom < 6) return 28;
  if (zoom < 9) return 34;
  return 40;
}

export function Map() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const dataRef = useRef<{ teams: FeatureCollection; events: FeatureCollection } | null>(null);
  const teamsListRef = useRef<MapTeam[]>([]);
  const eventsListRef = useRef<MapEvent[]>([]);
  const eventsZoomRef = useRef<number>(-1);
  const markersRef = useRef<globalThis.Map<number, maplibregl.Marker>>(new globalThis.Map());
  const moveDebounceRef = useRef<number | undefined>(undefined);
  const updateMarkersRef = useRef<() => void>(() => {});
  const refreshEventsRef = useRef<() => void>(() => {});
  const layersRef = useRef<LayerState>(INITIAL_LAYERS);
  const projectionRef = useRef<Projection>("mercator");
  const interactionsAddedRef = useRef(false);
  const styleReadyRef = useRef(false);
  const styleFellBackRef = useRef(false);
  const districtsRequestedRef = useRef(false);
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  const [searchParams] = useSearchParams();
  const focusTeamParam = searchParams.get("team");
  const focusAppliedRef = useRef<string | null>(null);

  const [projection, setProjection] = useState<Projection>("mercator");
  const [layers, setLayers] = useState<LayerState>(INITIAL_LAYERS);
  const [mapReady, setMapReady] = useState(false);

  const teamsQuery = useMapTeams();
  const eventsQuery = useMapEvents(CURRENT_YEAR);

  const teams = useMemo(() => teamsQuery.data?.teams ?? [], [teamsQuery.data]);
  const events = useMemo(() => eventsQuery.data?.events ?? [], [eventsQuery.data]);
  const teamsGeo = useMemo(() => teamsToGeoJSON(teams) as FeatureCollection, [teams]);
  const eventsGeo = useMemo(() => eventsToGeoJSON(events) as FeatureCollection, [events]);

  useEffect(() => {
    document.title = "Map - Peekorobo";
  }, []);

  const openPopup = useCallback((coords: [number, number], html: string) => {
    const map = mapRef.current;
    if (!map) return;
    popupRef.current?.remove();
    popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "300px", offset: 12 })
      .setLngLat(coords)
      .setHTML(html)
      .addTo(map);
  }, []);

  const applyDistrictLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    if (map.getSource("districts")) return;
    if (districtsRequestedRef.current) return;
    districtsRequestedRef.current = true;
    fetch(DISTRICTS_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`districts ${r.status}`))))
      .then((geo: FeatureCollection) => {
        const m = mapRef.current;
        if (!m || m.getSource("districts")) return;
        m.addSource("districts", { type: "geojson", data: geo });
        const beforeId = m.getLayer("teams-clusters") ? "teams-clusters" : undefined;
        m.addLayer(
          {
            id: "districts-fill",
            type: "fill",
            source: "districts",
            paint: { "fill-color": ["get", "color"], "fill-opacity": 0.22 },
            layout: { visibility: layersRef.current.districts ? "visible" : "none" },
          },
          beforeId,
        );
        m.addLayer(
          {
            id: "districts-outline",
            type: "line",
            source: "districts",
            paint: { "line-color": ["get", "color"], "line-width": 1.2, "line-opacity": 0.8 },
            layout: { visibility: layersRef.current.districts ? "visible" : "none" },
          },
          beforeId,
        );
      })
      .catch(() => {
        districtsRequestedRef.current = false;
      });
  }, []);

  const addDataLayers = useCallback(() => {
    const map = mapRef.current;
    const data = dataRef.current;
    if (!map || !styleReadyRef.current || !data) return;
    if (map.getSource("teams-heat")) return;

    // Teams render as viewport-culled HTML avatar markers (see updateTeamMarkers),
    // not a GL source. This non-clustered source only backs the density heatmap.
    map.addSource("teams-heat", { type: "geojson", data: data.teams });
    // Events are never clustered: every event shows as its own colored point.
    map.addSource("events", { type: "geojson", data: data.events });

    map.addLayer({
      id: "teams-heat",
      type: "heatmap",
      source: "teams-heat",
      layout: { visibility: layersRef.current.heatmap ? "visible" : "none" },
      paint: {
        "heatmap-weight": 1,
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 0.5, 9, 1.4],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 8, 6, 18, 12, 35],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 0, 0.85, 12, 0.5],
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0, "rgba(0,0,0,0)",
          0.2, "#313695",
          0.4, "#4575b4",
          0.6, "#fee090",
          0.8, "#f46d43",
          1, "#a50026",
        ],
      },
    });

    map.addLayer({
      id: "events-points",
      type: "circle",
      source: "events",
      layout: { visibility: layersRef.current.events ? "visible" : "none" },
      paint: {
        "circle-color": ["get", "color"],
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 4, 8, 6, 12, 8],
        "circle-stroke-width": 1.2,
        "circle-stroke-color": "#ffffff",
        "circle-opacity": 0.95,
      },
    });

    if (!interactionsAddedRef.current) {
      interactionsAddedRef.current = true;

      map.on("click", "events-points", (e) => {
        // Include every event under the cursor / same venue stack, not just the top feature.
        const hits =
          map.queryRenderedFeatures(e.point, { layers: ["events-points"] }) ?? e.features ?? [];
        if (hits.length === 0) return;
        const propsList = hits
          .map((f) => f.properties as unknown as EventFeatureProps)
          .filter((p) => p?.event_key);
        // De-dupe by event_key (query can return duplicates across tiles).
        const seen = new Set<string>();
        const unique: EventFeatureProps[] = [];
        for (const p of propsList) {
          if (seen.has(p.event_key)) continue;
          seen.add(p.event_key);
          unique.push(p);
        }
        const first = hits[0];
        const coords = (
          first.geometry as unknown as { coordinates: [number, number] }
        ).coordinates.slice() as [number, number];
        if (unique.length === 1) {
          openPopup(coords, eventPopupHTML(unique[0]));
        } else {
          openPopup(
            coords,
            stackPopupHTML(
              "events here",
              unique.map((p) => eventStackRowHTML(p)),
            ),
          );
        }
      });

      map.on("mouseenter", "events-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "events-points", () => {
        map.getCanvas().style.cursor = "";
      });
    }
  }, [openPopup]);

  // Viewport-culled team avatar markers. Only teams within the current bounds
  // (plus a buffer) get a live DOM marker; markers are pooled by team number and
  // removed when they scroll out of view, keeping the live count bounded.
  // Co-located teams are fanned out in a small ring so avatars aren't buried.
  const updateTeamMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    const markers = markersRef.current;

    if (!layersRef.current.teams) {
      markers.forEach((m) => m.remove());
      markers.clear();
      return;
    }

    const teamsList = teamsListRef.current;
    if (teamsList.length === 0) return;

    const b = map.getBounds();
    const west = b.getWest();
    const east = b.getEast();
    const south = b.getSouth();
    const north = b.getNorth();
    const dx = (east - west) * 0.2;
    const dy = (north - south) * 0.2;
    const size = avatarSizeForZoom(map.getZoom());

    const desired: MapTeam[] = [];
    for (const t of teamsList) {
      if (t.lng >= west - dx && t.lng <= east + dx && t.lat >= south - dy && t.lat <= north + dy) {
        desired.push(t);
        if (desired.length >= MAX_TEAM_MARKERS) break;
      }
    }
    const spread = spreadByCoords(
      desired,
      (t) => ({ lat: t.lat, lng: t.lng }),
      stackRadiusForZoom(map.getZoom(), b.getCenter().lat),
      (t) => t.team_number,
    );
    const byNumber = new globalThis.Map(spread.map((s) => [s.item.team_number, s] as const));
    const desiredKeys = new Set(byNumber.keys());

    markers.forEach((m, key) => {
      if (!desiredKeys.has(key)) {
        m.remove();
        markers.delete(key);
      }
    });

    for (const placed of spread) {
      const t = placed.item;
      const existing = markers.get(t.team_number);
      if (existing) {
        existing.setLngLat([placed.lng, placed.lat]);
        const el = existing.getElement();
        if (el.style.width !== `${size}px`) {
          el.style.width = `${size}px`;
          el.style.height = `${size}px`;
        }
        continue;
      }
      const img = document.createElement("img");
      img.className = "peeko-team-marker";
      img.src = teamAvatar(t.team_number);
      img.loading = "lazy";
      img.alt = `Team ${t.team_number}`;
      img.style.width = `${size}px`;
      img.style.height = `${size}px`;
      img.addEventListener("error", () => {
        if (!img.src.endsWith("stock.png")) img.src = STOCK_AVATAR;
      });
      img.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const key = coordKey(placed.trueLat, placed.trueLng);
        const neighbors = teamsListRef.current.filter(
          (x) => coordKey(x.lat, x.lng) === key,
        );
        if (neighbors.length <= 1) {
          openPopup([placed.lng, placed.lat], teamPopupHTML(teamToPopupProps(t)));
        } else {
          openPopup(
            [placed.trueLng, placed.trueLat],
            stackPopupHTML(
              "teams here",
              neighbors.map((n) => teamStackRowHTML(teamToPopupProps(n))),
            ),
          );
        }
      });
      const marker = new maplibregl.Marker({ element: img, anchor: "center" })
        .setLngLat([placed.lng, placed.lat])
        .addTo(map);
      markers.set(t.team_number, marker);
    }
  }, [openPopup]);

  // Refresh event point spread when zoom changes enough that the ring radius moves.
  const refreshEventSpread = useCallback(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    const zoom = map.getZoom();
    // Skip tiny zoom jitter; radius formula is stepwise enough via continuous fn.
    if (Math.abs(zoom - eventsZoomRef.current) < 0.35 && eventsZoomRef.current >= 0) return;
    eventsZoomRef.current = zoom;
    const src = map.getSource("events") as GeoJSONSource | undefined;
    if (!src) return;
    const geo = eventsToGeoJSON(eventsListRef.current, zoom, map.getCenter().lat) as FeatureCollection;
    if (dataRef.current) dataRef.current.events = geo;
    src.setData(geo);
  }, []);

  updateMarkersRef.current = updateTeamMarkers;
  refreshEventsRef.current = refreshEventSpread;

  // Create the map once on mount; tear it down on unmount (no hot-reload leaks).
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const map = new maplibregl.Map({
      container,
      style: BASEMAP_PRIMARY,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: 2,
      maxZoom: 18,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

    map.on("style.load", () => {
      styleReadyRef.current = true;
      map.setProjection({ type: projectionRef.current });
      applySky(map, projectionRef.current);
      addDataLayers();
      if (layersRef.current.districts) applyDistrictLayer();
      updateMarkersRef.current();
      refreshEventsRef.current();
      setMapReady(true);
    });

    const onMoveEnd = () => {
      if (moveDebounceRef.current) window.clearTimeout(moveDebounceRef.current);
      moveDebounceRef.current = window.setTimeout(() => {
        updateMarkersRef.current();
        refreshEventsRef.current();
      }, 120);
    };
    map.on("moveend", onMoveEnd);

    map.on("error", (e) => {
      const msg = String((e as { error?: { message?: string } }).error?.message ?? "");
      if (!styleFellBackRef.current && /style|glyph|sprite|tile/i.test(msg)) {
        styleFellBackRef.current = true;
        interactionsAddedRef.current = false;
        styleReadyRef.current = false;
        try {
          map.setStyle(BASEMAP_FALLBACK);
        } catch {
          // ignore
        }
      }
    });

    // Route SPA links inside popups through react-router.
    const onContainerClick = (ev: MouseEvent) => {
      const target = (ev.target as HTMLElement | null)?.closest("[data-spa-href]");
      if (target) {
        ev.preventDefault();
        const href = target.getAttribute("data-spa-href");
        if (href) {
          popupRef.current?.remove();
          navigateRef.current(href);
        }
      }
    };
    container.addEventListener("click", onContainerClick);

    const resize = () => map.resize();
    const raf = requestAnimationFrame(resize);
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      if (moveDebounceRef.current) window.clearTimeout(moveDebounceRef.current);
      container.removeEventListener("click", onContainerClick);
      markersRef.current.forEach((m) => m.remove());
      markersRef.current.clear();
      popupRef.current?.remove();
      popupRef.current = null;
      map.remove();
      mapRef.current = null;
      interactionsAddedRef.current = false;
      districtsRequestedRef.current = false;
      styleReadyRef.current = false;
      setMapReady(false);
    };
  }, [addDataLayers, applyDistrictLayer]);

  // Push new data into the sources (or create them if the style is already up).
  useEffect(() => {
    dataRef.current = { teams: teamsGeo, events: eventsGeo };
    teamsListRef.current = teams;
    eventsListRef.current = events;
    eventsZoomRef.current = -1; // force respread at current zoom
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    const heatSrc = map.getSource("teams-heat") as GeoJSONSource | undefined;
    if (heatSrc) {
      heatSrc.setData(teamsGeo);
      refreshEventSpread();
    } else {
      addDataLayers();
    }
    updateTeamMarkers();
  }, [teams, teamsGeo, events, eventsGeo, mapReady, addDataLayers, updateTeamMarkers, refreshEventSpread]);

  // Projection toggle (2D mercator <-> 3D globe).
  useEffect(() => {
    projectionRef.current = projection;
    const map = mapRef.current;
    if (map && styleReadyRef.current) {
      map.setProjection({ type: projection });
      applySky(map, projection);
      requestAnimationFrame(() => map.resize());
    }
  }, [projection]);

  // Layer visibility toggles.
  useEffect(() => {
    layersRef.current = layers;
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;

    const setVis = (id: string, visible: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    };
    setVis("events-points", layers.events);
    setVis("teams-heat", layers.heatmap);
    setVis("districts-fill", layers.districts);
    setVis("districts-outline", layers.districts);

    updateTeamMarkers();
    if (layers.districts) applyDistrictLayer();
  }, [layers, mapReady, applyDistrictLayer, updateTeamMarkers]);

  const handleLayerChange = useCallback((key: keyof LayerState, value: boolean) => {
    setLayers((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSearchSelect = useCallback(
    (result: MapSearchResult) => {
      const map = mapRef.current;
      if (!map) return;
      if (result.type === "team") {
        const t: MapTeam = result.team;
        map.flyTo({ center: [t.lng, t.lat], zoom: 10, speed: 1.4 });
        openPopup([t.lng, t.lat], teamPopupHTML(teamToPopupProps(t)));
      } else {
        const ev: MapEvent = result.event;
        map.flyTo({ center: [ev.lng, ev.lat], zoom: 10, speed: 1.4 });
        openPopup(
          [ev.lng, ev.lat],
          eventPopupHTML({
            kind: "event",
            event_key: ev.event_key,
            name: ev.name ?? ev.event_key,
            location: locationString(ev.city ?? "", ev.state_prov ?? "", ev.country ?? ""),
            event_type: ev.event_type ?? "",
            week: eventWeekLabel(ev.week) ?? "",
            dates: formatDateRange(ev.start_date, ev.end_date),
            color: eventTypeColor(ev.event_type),
          }),
        );
      }
    },
    [openPopup],
  );

  const isLoading = teamsQuery.isLoading || eventsQuery.isLoading;
  const error = teamsQuery.error || eventsQuery.error;

  // Deep link: /map?team=254 flies to that team once map + data are ready.
  useEffect(() => {
    if (!mapReady || isLoading) return;
    if (!focusTeamParam) {
      focusAppliedRef.current = null;
      return;
    }
    if (focusAppliedRef.current === focusTeamParam) return;
    const num = Number(focusTeamParam);
    if (!Number.isFinite(num) || num <= 0) return;
    const t = teams.find((x) => x.team_number === num);
    if (!t) return;
    focusAppliedRef.current = focusTeamParam;
    const id = window.setTimeout(() => {
      handleSearchSelect({ type: "team", team: t });
    }, 120);
    return () => window.clearTimeout(id);
  }, [mapReady, isLoading, focusTeamParam, teams, handleSearchSelect]);

  return (
    <Box
      className="peeko-map"
      style={{
        position: "relative",
        width: "100%",
        height: "calc(100dvh - 60px)",
        overflow: "hidden",
        background: "#0f0f0f",
      }}
    >
      {error ? (
        <Box p="md">
          <ErrorState error={error} />
        </Box>
      ) : (
        <>
          <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />

          <MapControls
            projection={projection}
            onProjectionChange={setProjection}
            layers={layers}
            onLayerChange={handleLayerChange}
            teamCount={teams.length}
            eventCount={events.length}
          />
          <MapSearch
            teams={teams}
            events={events}
            onSelect={handleSearchSelect}
            seedQuery={focusTeamParam}
          />

          {isLoading ? (
            <Overlay color="#0f0f0f" backgroundOpacity={0.6} zIndex={4}>
              <Stack align="center" justify="center" h="100%" gap="xs">
                <Loader color="peeko" />
                <Text size="sm" c="dimmed">
                  Loading map data...
                </Text>
              </Stack>
            </Overlay>
          ) : null}
        </>
      )}
    </Box>
  );
}
