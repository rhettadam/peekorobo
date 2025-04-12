from layouts.topbar import topbar, footer
from dash import html
import dash_bootstrap_components as dbc

blog_layout = html.Div([
    topbar,
    dbc.Container([
        html.H2("ACE (Adjusted Contribution Estimate) Algorithm", className="text-center my-4"),

        html.P("The EPA (Estimated Points Added) model attempts to estimate a team's contribution to a match based on detailed scoring breakdowns and long-term trends. ACE (Adjusted Contribution Estimate) extends this by incorporating consistency, alliance context, and statistical reliability.", style={"fontSize": "1.1rem"}),

        html.H4("Core Model", className="mt-4"),
        html.P("EPA updates are done incrementally after each match. Auto, Teleop, and Endgame contributions are calculated, then EPA is updated using a weighted delta."),

        dbc.Card([
            dbc.CardHeader("EPA Update"),
            dbc.CardBody([
                html.Pre("""
# Delta calculation with decay and match importance:
delta = decay * (K / (1 + M)) * ((actual - epa) - M * (opponent_score - epa))

# Update EPA:
epa += delta
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Decay and Match Weighting"),
        html.P("EPA uses exponential decay so newer matches matter more. Quals are weighted more than playoffs to reduce alliance bias."),

        dbc.Card([
            dbc.CardHeader("Decay Formula"),
            dbc.CardBody([
                html.Pre("""
decay = 0.95 ** match_index
importance = {"qm": 1.2, "qf": 1.0, "sf": 1.0, "f": 1.0}
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("EPA Component Breakdown"),
        html.P("Each team’s total EPA is the sum of their estimated Auto, Teleop, and Endgame contributions. These are computed separately and updated using the same delta mechanism."),

        html.H4("Auto EPA Estimation"),
        html.P("Auto EPA estimates scoring using reef row counts. To reduce inflation, the algorithm trims the top 25% of scores and caps the result."),

        dbc.Card([
            dbc.CardHeader("Auto Scoring Logic"),
            dbc.CardBody([
                html.Pre("""
def estimate_consistent_auto(breakdowns, team_count):
    scores = sorted(score_per_breakdown(b) for b in breakdowns)
    cutoff = int(len(scores) * 0.75)
    trimmed = scores[:cutoff]
    return round(min(statistics.mean(trimmed), 30), 2)
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Statistical Notes on Auto EPA"),
        html.P("The trimming method approximates a robust mean, reducing influence from occasional hot autos. It’s a simplified Winsorized mean. The cap of 30 points is based on expected maximum scoring in auto under typical match constraints."),

        html.H4("Confidence Weighting (ACE)"),
        html.P("ACE = EPA × Confidence. Confidence is computed from three components: consistency, rookie bonus, and carry factor."),

        dbc.Card([
            dbc.CardHeader("ACE Confidence Formula"),
            dbc.CardBody([
                html.Pre("""
consistency = 1 - (stdev / mean)
rookie_bonus = 1.0 if veteran else 0.6
carry = min(1.0, team_epa / (avg_teammate_epa + ε))
confidence = (consistency + rookie_bonus + carry) / 3
ACE = EPA × confidence
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Consistency"),
        html.P("This measures how stable a team's match-to-match performance is. Statistically, it's computed as 1 minus the coefficient of variation (CV):"),

        dbc.Card([
            dbc.CardHeader("Consistency"),
            dbc.CardBody([
                html.Pre("""
consistency = 1 - (statistics.stdev(scores) / statistics.mean(scores))
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Rookie Bonus"),
        html.P("Veteran teams start with a higher confidence (1.0 vs 0.6) because they’ve historically performed more predictably."),

        html.H4("Carry Factor"),
        html.P("This measures whether a team is likely benefiting from stronger alliance partners. A team well below its average teammates gets a lower confidence score."),

        html.Hr(),
        html.P("The full model is continuously evolving and improving. To contribute, test ideas, or file issues, visit the GitHub repository:", className="mt-4"),
        html.A("https://github.com/rhettadam/peekorobo", href="https://github.com/rhettadam/peekorobo", target="_blank")
    ], style={"maxWidth": "900px"}, className="py-4 mx-auto"),
    dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
    dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
    dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
    footer
])