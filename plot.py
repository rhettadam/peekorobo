import plotly.graph_objects as go

def generate_rank_over_time_plot(selected_team, rank_type):
    years_participated = selected_team["years_participated"]
    ranks = []

    for year in years_participated:
        file_path = f"team_data/teams_{year}.json"
        if not os.path.exists(file_path):
            ranks.append(None)
            continue

        with open(file_path, "r") as f:
            team_data = json.load(f)

        global_rank, country_rank, state_rank = calculate_ranks(team_data, selected_team)

        if rank_type == "state":
            ranks.append(state_rank)
        elif rank_type == "country":
            ranks.append(country_rank)
        elif rank_type == "global":
            ranks.append(global_rank)

    return go.Figure(
        data=go.Scatter(x=years_participated, y=ranks, mode="lines+markers", name=f"{rank_type.title()} Rank"),
        layout=go.Layout(
            title=f"{rank_type.title()} Rank Over Time",
            xaxis=dict(title="Year"),
            yaxis=dict(title="Rank", autorange="reversed"),  # Rank 1 is the best
        ),
    )

def generate_awards_over_time_plot(selected_team):
    awards = tba_get(f"team/{selected_team['team_number']}/awards")
    awards_by_year = {}

    for award in awards:
        year = award["year"]
        awards_by_year[year] = awards_by_year.get(year, 0) + 1

    years = sorted(awards_by_year.keys())
    counts = [awards_by_year[year] for year in years]

    return go.Figure(
        data=go.Bar(x=years, y=counts, name="Awards"),
        layout=go.Layout(
            title="Awards Over Time",
            xaxis=dict(title="Year"),
            yaxis=dict(title="Number of Awards"),
        ),
    )

def generate_win_loss_ratio_plot(selected_team):
    matches_by_year = {}

    for year in selected_team["years_participated"]:
        matches = tba_get(f"team/{selected_team['team_number']}/matches/{year}")
        if matches:
            wins = sum(
                1
                for match in matches
                if (match["winning_alliance"] == "red" and selected_team["team_key"] in match["alliances"]["red"]["team_keys"])
                or (match["winning_alliance"] == "blue" and selected_team["team_key"] in match["alliances"]["blue"]["team_keys"])
            )
            total_matches = len(matches)
            win_loss_ratio = wins / total_matches if total_matches > 0 else 0
            matches_by_year[year] = win_loss_ratio

    years = sorted(matches_by_year.keys())
    ratios = [matches_by_year[year] for year in years]

    return go.Figure(
        data=go.Scatter(x=years, y=ratios, mode="lines+markers", name="Win/Loss Ratio"),
        layout=go.Layout(
            title="Win/Loss Ratio Over Time",
            xaxis=dict(title="Year"),
            yaxis=dict(title="Win/Loss Ratio"),
        ),
    )
