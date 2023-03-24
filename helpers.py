from datetime import datetime


def round_suffix(rank: int) -> str:
    ith = {1: "st", 2: "nd", 3: "rd"}.get(
        rank % 10 * (rank % 100 not in [11, 12, 13]), "th"
    )
    return f"{str(rank)}{ith}"


def dedupe(lst):
    dup_free_set = set()
    for x in lst:
        t = tuple(x)
        if t not in dup_free_set:
            dup_free_set.add(t)
    return list(dup_free_set)


def seconds_text(refresh_time: int, nowtime: datetime.utcnow()) -> str:
    secs = round((nowtime - datetime.utcfromtimestamp(refresh_time)).total_seconds())
    if secs > 60:
        days = secs // 86400
        hours = (secs - days * 86400) // 3600
        minutes = (secs - days * 86400 - hours * 3600) // 60
        result = (
            ("{} days, ".format(days) if days else "")
            + ("{} hours, ".format(hours) if hours else "")
            + ("{} minutes, ".format(minutes) if minutes else "")
        )
        return result[0:-2]
    else:
        return "0 minutes"


def render_players(players: list, rank_type: str):
    starting_qbs = [
        player
        for player in players
        if player["fantasy_position"] == "QB"
        if player["fantasy_designation"] == "STARTER"
    ]
    starting_rbs = [
        player
        for player in players
        if player["fantasy_position"] == "RB"
        if player["fantasy_designation"] == "STARTER"
    ]
    starting_wrs = [
        player
        for player in players
        if player["fantasy_position"] == "WR"
        if player["fantasy_designation"] == "STARTER"
    ]
    starting_tes = [
        player
        for player in players
        if player["fantasy_position"] == "TE"
        if player["fantasy_designation"] == "STARTER"
    ]
    flex = [player for player in players if player["fantasy_position"] == "FLEX"]
    super_flex = [
        player for player in players if player["fantasy_position"] == "SUPER_FLEX"
    ]
    rec_flex = [
        player for player in players if player["fantasy_position"] == "REC_FLEX"
    ]
    bench_qbs = [
        player
        for player in players
        if player["fantasy_position"] == "QB"
        if player["fantasy_designation"] == "BENCH"
    ]
    bench_rbs = [
        player
        for player in players
        if player["fantasy_position"] == "RB"
        if player["fantasy_designation"] == "BENCH"
    ]
    bench_wrs = [
        player
        for player in players
        if player["fantasy_position"] == "WR"
        if player["fantasy_designation"] == "BENCH"
    ]
    bench_tes = [
        player
        for player in players
        if player["fantasy_position"] == "TE"
        if player["fantasy_designation"] == "BENCH"
    ]

    starters = {
        "qb": starting_qbs,
        "rb": starting_rbs,
        "wr": starting_wrs,
        "te": starting_tes,
        "flex": flex,
        "super_flex": super_flex,
        "rec_flex": rec_flex,
    }

    bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}

    if rank_type == "power":
        picks = [
            player for player in players if player["fantasy_designation"] == "PICKS"
        ]
        picks_ = {"picks": picks}
        team_spots = {"starters": starters, "bench": bench, "picks": picks_}
    elif rank_type == "contender":
        team_spots = {"starters": starters, "bench": bench}

    return team_spots
