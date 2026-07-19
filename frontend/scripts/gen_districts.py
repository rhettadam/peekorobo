"""One-off: build a small FRC-district boundaries GeoJSON for the /map overlay.

Fetches Natural Earth 1:50m admin-1 states/provinces, filters to the states and
provinces that make up FRC districts, tags each feature with its district code +
color, trims properties, and writes frontend/public/data/districts.geojson.
"""
import json
import os
import urllib.request

NE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_1_states_provinces.geojson"
)

DISTRICT_STATES = {
    "ONT": ["Ontario"],
    "FMA": ["Delaware", "New Jersey", "Pennsylvania"],
    "FCH": ["Maryland", "Virginia", "District of Columbia"],
    "FIT": ["Texas", "New Mexico"],
    "PCH": ["Georgia"],
    "PNW": ["Washington", "Oregon"],
    "FIM": ["Michigan"],
    "FSC": ["South Carolina"],
    "FNC": ["North Carolina"],
    "FIN": ["Indiana"],
    "NE": ["Connecticut", "Massachusetts", "Maine", "New Hampshire", "Vermont"],
    "CA": ["California"],
    "WIN": ["Wisconsin"],
}

DISTRICT_COLORS = {
    "ONT": "#1f77b4", "FMA": "#ff7f0e", "ISR": "#2ca02c", "FCH": "#d62728",
    "FIT": "#9467bd", "PCH": "#8c564b", "PNW": "#e377c2", "FIM": "#17becf",
    "FSC": "#bcbd22", "FNC": "#17becf", "FIN": "#ff9896", "NE": "#98df8a",
    "CA": "#00bfff", "WIN": "#ff7f0e",
}

STATE_TO_DISTRICT = {s: d for d, states in DISTRICT_STATES.items() for s in states}


def main():
    print(f"Fetching {NE_URL} ...")
    with urllib.request.urlopen(NE_URL) as resp:
        data = json.load(resp)

    features = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        name = props.get("name")
        admin = props.get("admin")
        district = STATE_TO_DISTRICT.get(name)
        if district is None and admin == "Israel":
            district = "ISR"
            name = name or "Israel"
        if district is None:
            continue
        feat["properties"] = {
            "name": name,
            "district": district,
            "color": DISTRICT_COLORS.get(district, "#808080"),
        }
        features.append(feat)

    out = {"type": "FeatureCollection", "features": features}
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "districts.geojson")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    size = os.path.getsize(out_path)
    print(f"Wrote {len(features)} features to {out_path} ({size:,} bytes)")


if __name__ == "__main__":
    main()
