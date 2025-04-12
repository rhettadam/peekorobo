from dash import html
import dash_bootstrap_components as dbc

def epa_legend_layout():
    return dbc.Alert(
        [
            html.H5("ACE Color Key (Percentile):", className="mb-3", style={"fontWeight": "bold"}),
            html.Div("🟣  ≥ 99% | 🔵  ≥ 95% | 🟢  ≥ 90% | 🟡  ≥ 75% | 🟠  ≥ 50% | 🔴  ≥ 25% | 🟤  < 25%"),
        ],
        color="light",
        style={
            "border": "1px solid #ccc",
            "borderRadius": "10px",
            "padding": "10px",
            "fontSize": "0.9rem",
        },
    )

def get_epa_display(epa, percentiles):

    if epa is None:
        return "N/A"

    if epa >= percentiles["99"]:
        color = "🟣"  # Purple
    elif epa >= percentiles["95"]:
        color = "🔵"  # Blue
    elif epa >= percentiles["90"]:
        color = "🟢"  # Green
    elif epa >= percentiles["75"]:
        color = "🟡"  # Yellow
    elif epa >= percentiles["50"]:
        color = "🟠"  # Orange
    elif epa >= percentiles["25"]:
        color = "🔴"  # Brown
    else:
        color = "🟤"  # Red

    return f"{color} {epa:.2f}"