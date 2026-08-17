import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, or_, func, case
from sqlalchemy.orm import Session, aliased

from data.models.event_matches import EventMatch, _parse_team_list, _team_in_list
from data.models.event_teams import EventTeams
from data.models.events import Events
from data.models.team_epas import TeamEpa
from data.models.teams import Teams, to_team_response
from query.games import (
    H2HAgainstStats,
    H2HMatch,
    H2HResponse,
    H2HTeamInfo,
    H2HTogetherStats,
    H2HYearSlice,
    PredictorMatch,
    PredictorMatchesResponse,
    PredictorQuery,
)

_COMP_ORD = case(
    (EventMatch.comp_level == "qm", 0),
    (EventMatch.comp_level == "ef", 1),
    (EventMatch.comp_level == "qf", 2),
    (EventMatch.comp_level == "sf", 3),
    (EventMatch.comp_level == "f", 4),
    else_=9,
)

_PLAYED = or_(
    EventMatch.red_score > 0,
    EventMatch.blue_score > 0,
    EventMatch.winning_alliance.in_(("red", "blue")),
)


def _year_of(event_key: Optional[str]) -> int:
    if event_key and len(event_key) >= 4 and event_key[:4].isdigit():
        return int(event_key[:4])
    return 0


def _empty_team(team_number: int) -> H2HTeamInfo:
    return H2HTeamInfo(team_number=team_number, nickname=f"Team {team_number}")


def _team_info(db: Session, team_number: int, year: Optional[int]) -> H2HTeamInfo:
    row = db.get(Teams, team_number)
    info = _empty_team(team_number)
    if row is not None:
        data = to_team_response(row)
        info = H2HTeamInfo(
            team_number=data.team_number,
            nickname=data.nickname or info.nickname,
            city=data.city or "",
            state_prov=data.state_prov or "",
            country=data.country or "",
            district_key=data.district_key,
            team_colors=data.team_colors,
        )
    if year is not None:
        epa = db.scalars(
            select(TeamEpa).where(TeamEpa.team_number == team_number, TeamEpa.year == year)
        ).first()
        if epa is not None:
            info.ace = float(epa.ace) if epa.ace is not None else None
            info.raw = float(epa.raw) if epa.raw is not None else None
            info.wins = int(epa.wins) if epa.wins is not None else None
            info.losses = int(epa.losses) if epa.losses is not None else None
            info.ties = int(epa.ties) if epa.ties is not None else None
            info.rank_global = int(epa.rank_global) if epa.rank_global is not None else None
    return info


def _shared_event_keys(db: Session, team_a: int, team_b: int, year: Optional[int]) -> List[str]:
    a = aliased(EventTeams)
    b = aliased(EventTeams)
    stmt = (
        select(a.event_key)
        .join(b, a.event_key == b.event_key)
        .where(a.team_number == team_a, b.team_number == team_b)
    )
    if year is not None:
        stmt = stmt.where(a.event_key.like(f"{year}%"))
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def _pct(num: int, den: int) -> Optional[float]:
    if den <= 0:
        return None
    return num / den


def _mean(xs: List[float]) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None


def get_h2h(db: Session, team_a: int, team_b: int, year: Optional[int] = None) -> H2HResponse:
    info_a = _team_info(db, team_a, year)
    info_b = _team_info(db, team_b, year)
    shared = _shared_event_keys(db, team_a, team_b, year)
    empty = H2HResponse(
        team_a=info_a,
        team_b=info_b,
        year=year,
        events_shared=len(shared),
        together=H2HTogetherStats(),
        against=H2HAgainstStats(),
    )
    if not shared:
        return empty

    stmt = (
        select(
            EventMatch,
            Events.name,
            Events.week,
        )
        .outerjoin(Events, Events.event_key == EventMatch.event_key)
        .where(
            EventMatch.event_key.in_(shared),
            or_(*_team_in_list(team_a)),
            or_(*_team_in_list(team_b)),
        )
        .order_by(
            Events.start_date.nulls_last(),
            EventMatch.event_key,
            _COMP_ORD,
            EventMatch.set_number,
            EventMatch.match_number,
        )
    )

    together_scores: List[float] = []
    together_opp: List[float] = []
    together_margins: List[float] = []
    against_a_scores: List[float] = []
    against_b_scores: List[float] = []
    together = H2HTogetherStats()
    against = H2HAgainstStats()
    year_acc: Dict[int, H2HYearSlice] = {}
    matches: List[H2HMatch] = []

    for row in db.execute(stmt).all():
        m: EventMatch = row[0]
        event_name = row[1]
        week = row[2]
        red = _parse_team_list(m.red_teams)
        blue = _parse_team_list(m.blue_teams)
        a_all = "red" if team_a in red else ("blue" if team_a in blue else None)
        b_all = "red" if team_b in red else ("blue" if team_b in blue else None)
        if a_all is None or b_all is None:
            continue
        relation = "together" if a_all == b_all else "against"
        y = _year_of(m.event_key)
        winner = (m.winning_alliance or "").strip().lower()
        red_score = int(m.red_score or 0)
        blue_score = int(m.blue_score or 0)
        played = red_score > 0 or blue_score > 0 or winner in ("red", "blue")

        slice_row = year_acc.get(y)
        if slice_row is None:
            slice_row = H2HYearSlice(year=y)
            year_acc[y] = slice_row

        if relation == "together":
            together.matches += 1
            slice_row.together += 1
            if played:
                own = red_score if a_all == "red" else blue_score
                opp = blue_score if a_all == "red" else red_score
                together_scores.append(float(own))
                together_opp.append(float(opp))
                together_margins.append(float(own - opp))
                if winner == a_all:
                    together.wins += 1
                    slice_row.together_wins += 1
                elif winner in ("red", "blue"):
                    together.losses += 1
                else:
                    together.ties += 1
        else:
            against.matches += 1
            slice_row.against += 1
            if played:
                a_score = red_score if a_all == "red" else blue_score
                b_score = red_score if b_all == "red" else blue_score
                against_a_scores.append(float(a_score))
                against_b_scores.append(float(b_score))
                if winner == a_all:
                    against.a_wins += 1
                    slice_row.a_wins += 1
                elif winner == b_all:
                    against.b_wins += 1
                    slice_row.b_wins += 1
                else:
                    against.ties += 1

        matches.append(
            H2HMatch(
                match_key=m.match_key or "",
                event_key=m.event_key or "",
                event_name=(event_name or None),
                year=y,
                week=week,
                comp_level=m.comp_level or "",
                match_number=m.match_number or 0,
                set_number=m.set_number or 0,
                red_teams=red,
                blue_teams=blue,
                red_score=red_score,
                blue_score=blue_score,
                winning_alliance=winner,
                relation=relation,
                a_alliance=a_all,
                b_alliance=b_all,
                youtube_key=m.youtube_key,
                red_win_prob=m.red_win_prob,
                blue_win_prob=m.blue_win_prob,
            )
        )

    together.win_pct = _pct(together.wins, together.wins + together.losses + together.ties)
    together.avg_score = _mean(together_scores)
    together.avg_opp_score = _mean(together_opp)
    together.avg_margin = _mean(together_margins)
    decided = against.a_wins + against.b_wins + against.ties
    against.a_win_pct = _pct(against.a_wins, decided)
    against.avg_a_score = _mean(against_a_scores)
    against.avg_b_score = _mean(against_b_scores)
    if against_a_scores and against_b_scores:
        against.avg_margin = _mean(
            [a - b for a, b in zip(against_a_scores, against_b_scores)]
        )

    return H2HResponse(
        team_a=info_a,
        team_b=info_b,
        year=year,
        events_shared=len(shared),
        together=together,
        against=against,
        by_year=sorted(year_acc.values(), key=lambda s: s.year, reverse=True),
        matches=matches,
    )


def _nicknames_for_events(db: Session, event_keys: List[str], team_numbers: List[int]) -> Dict[str, str]:
    if not event_keys or not team_numbers:
        return {}
    stmt = select(EventTeams.team_number, EventTeams.nickname).where(
        EventTeams.event_key.in_(event_keys),
        EventTeams.team_number.in_(team_numbers),
    )
    out: Dict[str, str] = {}
    for tn, nick in db.execute(stmt).all():
        key = str(int(tn))
        if key not in out and nick:
            out[key] = str(nick).strip()
    missing = [n for n in team_numbers if str(n) not in out]
    if missing:
        for row in db.scalars(select(Teams).where(Teams.team_number.in_(missing))).all():
            out[str(int(row.team_number))] = (row.nickname or "").strip() or f"Team {row.team_number}"
    return out


def _is_played_row(m: EventMatch) -> bool:
    winner = (m.winning_alliance or "").strip().lower()
    return (m.red_score or 0) > 0 or (m.blue_score or 0) > 0 or winner in ("red", "blue")


def _to_predictor_match(m: EventMatch, event_name: str, week: Optional[int], event_type: Optional[str]) -> Optional[PredictorMatch]:
    winner = (m.winning_alliance or "").strip().lower()
    if winner not in ("red", "blue"):
        return None
    red = _parse_team_list(m.red_teams)
    blue = _parse_team_list(m.blue_teams)
    if len(red) < 1 or len(blue) < 1:
        return None
    if m.red_win_prob is None and m.blue_win_prob is None:
        return None
    return PredictorMatch(
        match_key=m.match_key or "",
        event_key=m.event_key or "",
        event_name=event_name or "",
        year=_year_of(m.event_key),
        week=week,
        event_type=event_type,
        comp_level=m.comp_level or "",
        match_number=m.match_number or 0,
        set_number=m.set_number or 0,
        red_teams=red,
        blue_teams=blue,
        red_score=int(m.red_score or 0),
        blue_score=int(m.blue_score or 0),
        winning_alliance=winner,
        red_win_prob=m.red_win_prob,
        blue_win_prob=m.blue_win_prob,
        red_predicted_score=m.red_predicted_score,
        blue_predicted_score=m.blue_predicted_score,
    )


def get_predictor_matches(db: Session, query: PredictorQuery) -> PredictorMatchesResponse:
    year = query.year
    playoff_levels = ("ef", "qf", "sf", "f")

    stmt = (
        select(EventMatch, Events.name, Events.week, Events.event_type)
        .outerjoin(Events, Events.event_key == EventMatch.event_key)
        .where(
            func.left(EventMatch.event_key, 4) == str(year),
            _PLAYED,
            or_(EventMatch.red_win_prob.is_not(None), EventMatch.blue_win_prob.is_not(None)),
        )
    )
    if query.event_key:
        stmt = stmt.where(EventMatch.event_key == query.event_key)
    if query.week is not None:
        stmt = stmt.where(Events.week == query.week)
    if query.playoffs_only:
        stmt = stmt.where(EventMatch.comp_level.in_(playoff_levels))

    stmt = stmt.order_by(
        Events.start_date.nulls_last(),
        EventMatch.event_key,
        _COMP_ORD,
        EventMatch.set_number,
        EventMatch.match_number,
    )

    rows = db.execute(stmt).all()
    parsed: List[Tuple[PredictorMatch, str]] = []
    for row in rows:
        m: EventMatch = row[0]
        if not _is_played_row(m):
            continue
        item = _to_predictor_match(m, row[1] or "", row[2], row[3])
        if item is None:
            continue
        parsed.append((item, m.event_key or ""))

    event_name: Optional[str] = None
    if query.event_key and parsed:
        event_name = parsed[0][0].event_name or None

    matches: List[PredictorMatch]
    if query.event_key:
        matches = [p[0] for p in parsed]
    else:
        rng = random.Random(query.seed)
        # Prefer spreading across events so the round isn't one regional.
        by_event: Dict[str, List[PredictorMatch]] = defaultdict(list)
        for item, ek in parsed:
            by_event[ek].append(item)
        event_keys = list(by_event.keys())
        rng.shuffle(event_keys)
        picked: List[PredictorMatch] = []
        # Round-robin take one match per event until we hit the limit.
        queues = {k: list(by_event[k]) for k in event_keys}
        for q in queues.values():
            rng.shuffle(q)
        while len(picked) < query.limit and queues:
            progressed = False
            for k in list(queues.keys()):
                if not queues[k]:
                    queues.pop(k, None)
                    continue
                picked.append(queues[k].pop())
                progressed = True
                if len(picked) >= query.limit:
                    break
            if not progressed:
                break
        matches = picked

    team_numbers: List[int] = []
    event_keys_used: List[str] = []
    seen_t = set()
    seen_e = set()
    for m in matches:
        if m.event_key and m.event_key not in seen_e:
            seen_e.add(m.event_key)
            event_keys_used.append(m.event_key)
        for t in (*m.red_teams, *m.blue_teams):
            if t not in seen_t:
                seen_t.add(t)
                team_numbers.append(t)

    return PredictorMatchesResponse(
        year=year,
        event_key=query.event_key,
        event_name=event_name,
        nicknames=_nicknames_for_events(db, event_keys_used, team_numbers),
        matches=matches,
    )
