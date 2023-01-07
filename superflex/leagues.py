import requests, uuid
import psycopg2
from psycopg2.extras import execute_batch, execute_values
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from datetime import datetime
from superflex.db import get_db, pg_db

bp = Blueprint("leagues", __name__, url_prefix="/")
bp.secret_key = "hello"


def n_user_id(user_name: str) -> str:
    user_url = f"https://api.sleeper.app/v1/user/{user_name}"
    un_res = requests.get(user_url)
    user_id = un_res.json()["user_id"]
    return user_id


def user_leagues(user_name: str, league_year: str) -> list:
    owner_id = n_user_id(user_name)
    leagues_url = (
        f"https://api.sleeper.app/v1/user/{owner_id}/leagues/nfl/{league_year}"
    )
    leagues_res = requests.get(leagues_url)
    leagues = []
    for league in leagues_res.json():
        qbs = len([i for i in league["roster_positions"] if i == "QB"])
        rbs = len([i for i in league["roster_positions"] if i == "RB"])
        wrs = len([i for i in league["roster_positions"] if i == "WR"])
        tes = len([i for i in league["roster_positions"] if i == "TE"])
        flexes = len([i for i in league["roster_positions"] if i == "FLEX"])
        super_flexes = len([i for i in league["roster_positions"] if i == "SUPER_FLEX"])
        rec_flexes = len([i for i in league["roster_positions"] if i == "REC_FLEX"])
        starters = sum([qbs, rbs, wrs, tes, flexes, super_flexes, rec_flexes])
        leagues.append(
            (
                league["name"],
                league["league_id"],
                league["avatar"],
                league["total_rosters"],
                qbs,
                rbs,
                wrs,
                tes,
                flexes,
                super_flexes,
                starters,
                len(league["roster_positions"]),
                league["sport"],
                rec_flexes,
                league["settings"]["type"],
                league_year,
            )
        )
    return leagues


def league_managers(league_id: str, user_id: str) -> list:
    managers = []
    for i in user_leagues(user_id):
        if i[1] in league_id:
            LEAGUE_ID = i[1]
            league_managers_url = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users"
            managers_res = requests.get(league_managers_url)
            for i in managers_res.json():
                a1 = (i["user_id"], i["display_name"], i["league_id"])
                managers.append(a1)
    return managers


def get_user_name(user_id: str):
    user_req = requests.get(f"https://api.sleeper.app/v1/user/{user_id}")
    user_meta = user_req.json()
    return (user_meta["username"], user_meta["display_name"])


def get_user_id(user_name: str) -> str:
    user_id_req = requests.get(f"https://api.sleeper.app/v1/user/{user_name}")
    return user_id_req.json()["user_id"]


def get_league_name(league_id: str) -> str:
    league_req = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    return league_req.json()["name"]


def get_users_data(league_id):
    users_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    return [
        (user_meta["display_name"], user_meta["user_id"], user_meta["avatar"])
        for user_meta in users_res.json()
    ]


def get_league_type(league_id: str):
    league_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    try:
        return (
            "sf_value"
            if "SUPER_FLEX" in league_res.json()["roster_positions"]
            else "one_qb_value"
        )
    except:
        return "sf_value"


def get_league_rosters_size(league_id: str) -> int:
    league_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    return league_res.json()["total_rosters"]


def get_league_rosters(league_id: str) -> list:
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    return rosters.json()


def get_traded_picks(league_id: str) -> list:
    total_res = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/traded_picks"
    )
    return total_res.json()


def get_full_league(league_id: str):
    l_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    return l_res.json()


def get_draft_id(league_id: str) -> str:
    draft = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts")
    draft_meta = draft.json()[0]
    return draft_meta


def get_draft(draft_id: str):
    draft_res = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}")
    return draft_res.json()


def get_managers(league_id: str) -> list:
    res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    manager_data = [
        ["sleeper", i["user_id"], league_id, i["avatar"], i["display_name"]]
        for i in res.json()
    ]
    return manager_data


def clean_league_managers(db, league_id: str):
    delete_query = f"""DELETE FROM dynastr.managers where league_id = '{league_id}' """
    cursor = db.cursor()
    cursor.execute(delete_query)
    db.commit()
    cursor.close()
    print("Managers deleted.")
    return


def insert_managers(db, managers: list):
    with db.cursor() as cursor:
        execute_values(
            cursor,
            """
                INSERT INTO dynastr.managers VALUES %s
                ON CONFLICT (user_id)
                DO UPDATE SET source = EXCLUDED.source
	                        , league_id = EXCLUDED.league_id
                            , avatar = EXCLUDED.avatar
                            , display_name = EXCLUDED.display_name;
                """,
            [
                (manager[0], manager[1], manager[2], manager[3], manager[4])
                for manager in iter(managers)
            ],
            page_size=1000,
        )
    return


def is_user(user_name: str) -> bool:
    res = requests.get(f"https://api.sleeper.app/v1/user/{user_name}")
    return True if res.text != "null" else False


def round_suffix(rank: int) -> str:
    ith = {1: "st", 2: "nd", 3: "rd"}.get(
        rank % 10 * (rank % 100 not in [11, 12, 13]), "th"
    )
    return f"{str(rank)}{ith}"


def clean_league_rosters(db, session_id: str, user_id: str, league_id: str):
    delete_query = f"""DELETE FROM dynastr.league_players where session_id = '{session_id}' and league_id = '{league_id}' """
    cursor = db.cursor()
    cursor.execute(delete_query)
    db.commit()
    cursor.close()
    print("Players deleted.")
    return


def clean_player_trades(db, league_id: str) -> None:
    delete_query = (
        f"""DELETE FROM dynastr.player_trades where league_id = '{league_id}'"""
    )
    cursor = db.cursor()
    cursor.execute(delete_query)
    db.commit()
    print("Player trades deleted")
    return


def clean_draft_trades(db, league_id: str) -> None:
    delete_query = (
        f"""DELETE FROM dynastr.draft_pick_trades where league_id = '{league_id}'"""
    )
    cursor = db.cursor()
    cursor.execute(delete_query)
    db.commit()
    print("Draft Picks Trades deleted")
    return


def clean_league_picks(db, league_id: str) -> None:
    delete_query = (
        f"""DELETE FROM dynastr.player_trades where league_id = '{league_id}'"""
    )
    cursor = db.cursor()
    cursor.execute(delete_query)
    cursor.close()
    print("Draft pick trades deleted")
    return


def get_sleeper_state():
    return requests.get("https://api.sleeper.app/v1/state/nfl").json()


def get_trades(league_id: str, nfl_state: dict) -> list:

    leg = nfl_state["leg"] if nfl_state["leg"] > 0 else 1
    print("leg", leg)
    all_trades = []
    week = 1
    for i in range(1, leg + 1):

        trans_call = requests.get(
            f"https://api.sleeper.app/v1/league/{league_id}/transactions/{week}"
        ).json()
        all_trades.extend(trans_call)
        week += 1
    trades_payload = [p for p in [i for i in all_trades] if p["type"] == "trade"]
    return trades_payload


def dedupe(lst):
    dup_free_set = set()
    for x in lst:
        t = tuple(x)
        if t not in dup_free_set:
            dup_free_set.add(t)
    return list(dup_free_set)


def insert_trades(db, trades: dict, league_id: str) -> None:
    player_adds_db = []
    player_drops_db = []
    draft_adds_db = []
    draft_drops_db = []

    for trade in trades:
        for roster_id in trade["roster_ids"]:
            player_adds = trade["adds"] if trade["adds"] else {}
            player_drops = trade["drops"] if trade["drops"] else {}
            draft_picks = trade["draft_picks"] if trade["draft_picks"] else [{}]

            for a_player_id, a_id in [
                [k, v] for k, v in player_adds.items() if v == roster_id
            ]:
                player_adds_db.append(
                    [
                        trade["transaction_id"],
                        trade["status_updated"],
                        a_id,
                        "add",
                        a_player_id,
                        league_id,
                    ]
                )
            for d_player_id, d_id in [
                [k, v] for k, v in player_drops.items() if v == roster_id
            ]:

                player_drops_db.append(
                    [
                        trade["transaction_id"],
                        trade["status_updated"],
                        d_id,
                        "drop",
                        d_player_id,
                        league_id,
                    ]
                )

            for pick in draft_picks:
                draft_picks_ = [v for k, v in pick.items()]

                if draft_picks_:
                    suffix = round_suffix(draft_picks_[1])
                    draft_adds_db.append(
                        [
                            trade["transaction_id"],
                            trade["status_updated"],
                            draft_picks_[4],
                            "add",
                            draft_picks_[0],
                            draft_picks_[1],
                            suffix,
                            draft_picks_[2],
                            league_id,
                        ]
                    )
                    draft_drops_db.append(
                        [
                            trade["transaction_id"],
                            trade["status_updated"],
                            draft_picks_[3],
                            "drop",
                            draft_picks_[0],
                            draft_picks_[1],
                            suffix,
                            draft_picks_[2],
                            league_id,
                        ]
                    )

    draft_adds_db = dedupe(draft_adds_db)
    player_adds_db = dedupe(player_adds_db)
    player_drops_db = dedupe(player_drops_db)
    draft_drops_db = dedupe(draft_drops_db)

    cursor = db.cursor()
    execute_batch(
        cursor,
        """INSERT INTO dynastr.draft_pick_trades (transaction_id, status_updated, roster_id, transaction_type, season, round, round_suffix, org_owner_id, league_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
    """,
        tuple(draft_adds_db),
        page_size=1000,
    )
    execute_batch(
        cursor,
        """INSERT INTO dynastr.draft_pick_trades (transaction_id, status_updated, roster_id, transaction_type, season, round, round_suffix, org_owner_id, league_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)  
    """,
        tuple(draft_drops_db),
        page_size=1000,
    )
    execute_batch(
        cursor,
        """INSERT INTO dynastr.player_trades (transaction_id, status_updated, roster_id, transaction_type, player_id, league_id)
    VALUES (%s, %s, %s, %s, %s, %s) 
    """,
        tuple(player_adds_db),
        page_size=1000,
    )
    execute_batch(
        cursor,
        """INSERT INTO dynastr.player_trades (transaction_id, status_updated, roster_id, transaction_type, player_id, league_id)
    VALUES (%s, %s, %s, %s, %s, %s) 
    """,
        tuple(player_drops_db),
        page_size=1000,
    )
    db.commit()
    cursor.close()
    return


def insert_league_rosters(db, session_id: str, user_id: str, league_id: str) -> None:
    league_players = []
    entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    rosters = get_league_rosters(league_id)

    for roster in rosters:
        league_roster = roster["players"]
        try:
            for player_id in league_roster:
                league_players.append(
                    [
                        session_id,
                        user_id,
                        player_id,
                        roster["league_id"],
                        roster["owner_id"]
                        if roster["owner_id"] is not None
                        else "EMPTY",
                        entry_time,
                    ]
                )
        except:
            league_players = []

    with db.cursor() as cursor:
        execute_values(
            cursor,
            """
                INSERT INTO dynastr.league_players VALUES %s
                ON CONFLICT (session_id, user_id, player_id)
                DO UPDATE SET league_id = EXCLUDED.league_id
                            , insert_date = EXCLUDED.insert_date;
                """,
            [
                (
                    league_player[0],
                    league_player[1],
                    league_player[2],
                    league_player[3],
                    league_player[4],
                    league_player[5],
                )
                for league_player in iter(league_players)
            ],
            page_size=1000,
        )

    return


def total_owned_picks(
    db, league_id: str, session_id, base_picks: dict = {}, traded_picks_all: dict = {}
) -> None:
    base_picks = {}
    traded_picks_all = {}
    league_size = get_league_rosters_size(league_id)
    total_picks = get_traded_picks(league_id)
    draft_id = get_draft_id(league_id)

    years = (
        [str(int(draft_id["season"]) + i) for i in range(1, 4)]
        if draft_id["status"] == "complete"
        else [str(int(draft_id["season"]) + i) for i in range(0, 3)]
    )
    rounds = [r for r in range(1, draft_id["settings"]["rounds"] + 1)]

    traded_picks = [
        [pick["season"], pick["round"], pick["roster_id"], pick["owner_id"]]
        for pick in total_picks
        if pick["roster_id"] != pick["owner_id"] and pick["season"] in years
    ]
    for year in years:
        base_picks[year] = {
            round: [[i, i] for i in range(1, league_size + 1)] for round in rounds
        }
        for pick in traded_picks:
            traded_picks_all[year] = {
                round: [
                    [i[2], i[3]]
                    for i in [i for i in traded_picks if i[0] == year and i[1] == round]
                ]
                for round in rounds
            }
    for year, traded_rounds in traded_picks_all.items():
        for round, picks in traded_rounds.items():
            for pick in picks:
                if [pick[0], pick[0]] in base_picks[year][round]:
                    base_picks[year][round].remove([pick[0], pick[0]])
                    base_picks[year][round].append(pick)

    for year, round in base_picks.items():
        for round, picks in round.items():
            draft_picks = [
                [
                    year,
                    round,
                    round_suffix(round),
                    pick[0],
                    pick[1],
                    league_id,
                    draft_id["draft_id"],
                    session_id,
                ]
                for pick in picks
            ]
            with db.cursor() as cursor:
                execute_values(
                    cursor,
                    """
                    INSERT INTO dynastr.draft_picks VALUES %s
                    ON CONFLICT (year, round, roster_id, owner_id, league_id, session_id)
                    DO UPDATE SET round_name = EXCLUDED.round_name
	                              , draft_id = EXCLUDED.draft_id;
                    """,
                    [
                        (
                            draft_pick[0],
                            draft_pick[1],
                            draft_pick[2],
                            draft_pick[3],
                            draft_pick[4],
                            draft_pick[5],
                            draft_pick[6],
                            draft_pick[7],
                        )
                        for draft_pick in iter(draft_picks)
                    ],
                    page_size=1000,
                )

    return


def clean_draft_positions(db, league_id: str):
    delete_query = (
        f"""DELETE FROM dynastr.draft_positions where league_id = '{league_id}'"""
    )
    cursor = db.cursor()
    cursor.execute(delete_query)
    cursor.close()
    print("Draft Positions Cleaned")
    return


def draft_positions(db, league_id: str, user_id: str, draft_order: list = []) -> None:
    draft_id = get_draft_id(league_id)
    draft = get_draft(draft_id["draft_id"])
    league = get_full_league(league_id)
    draft_order = []
    draft_dict = draft["draft_order"]
    draft_slot = {k: v for k, v in draft["slot_to_roster_id"].items() if v is not None}

    if len(draft["draft_order"]) < len(draft["slot_to_roster_id"]):
        empty_team_cnt = 0
        for k, v in draft_slot.items():
            if int(k) not in list(draft["draft_order"].values()):
                # print("DRAFT_POSITION", k, "ROSTER_ID", v)
                if league[v - 1]["owner_id"] is not None:
                    draft_dict[league[v - 1]["owner_id"]] = int(k)
                else:
                    empty_alias = f"Empty_Team{empty_team_cnt}"
                    draft_dict[empty_alias] = v
                    empty_team_cnt += 1

    season = draft["season"]
    rounds = draft_id["settings"]["rounds"]
    roster_slot = {int(k): v for k, v in draft_slot.items() if v is not None}
    rs_dict = dict(sorted(roster_slot.items(), key=lambda item: int(item[0])))

    try:
        draft_order_dict = dict(sorted(draft_dict.items(), key=lambda item: item[1]))
    except:
        # if no draft is present then create all managers at mid level for picks
        draft_order_dict = {i[0]: 5 for i in league_managers(league_id, user_id)}

    draft_order_ = dict([(value, key) for key, value in draft_order_dict.items()])

    for draft_position, roster_id in rs_dict.items():
        if draft_position <= 4:
            position_name = "Early"
        elif draft_position <= 8:
            position_name = "Mid"
        else:
            position_name = "Late"
        if int(draft_position) in [
            int(draft_position) for user_id, draft_position in draft_order_dict.items()
        ]:
            draft_order.append(
                [
                    season,
                    rounds,
                    draft_position,
                    position_name,
                    roster_id,
                    draft_order_[int(draft_position)],
                    # draft_order_.get(int(draft_position), "Empty"),
                    league_id,
                    draft_id["draft_id"],
                ]
            )
    cursor = db.cursor()
    execute_batch(
        cursor,
        """INSERT into dynastr.draft_positions (season, rounds,  position, position_name, roster_id, user_id, league_id, draft_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (season, rounds, position, user_id, league_id)
    DO UPDATE SET position_name = EXCLUDED.position_name
            , roster_id = EXCLUDED.roster_id
            , draft_id = EXCLUDED.draft_id
    ;""",
        tuple(draft_order),
        page_size=1000,
    )
    db.commit()
    cursor.close()
    return


def insert_current_leagues(
    db, session_id: str, user_id: str, user_name: str, entry_time: str, leagues: list
) -> None:
    cursor = db.cursor()
    execute_batch(
        cursor,
        """INSERT INTO dynastr.current_leagues (session_id, user_id, user_name, league_id, league_name, avatar, total_rosters, qb_cnt, rb_cnt, wr_cnt, te_cnt, flex_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
   ON CONFLICT (session_id, league_id) DO UPDATE 
  SET user_id = excluded.user_id,
  		user_name = excluded.user_name,
		league_id = excluded.league_id,
		league_name = excluded.league_name,
		avatar = excluded.avatar,
		total_rosters = excluded.total_rosters,
		qb_cnt = excluded.qb_cnt,
		rb_cnt = excluded.rb_cnt,
		wr_cnt = excluded.wr_cnt,
		te_cnt = excluded.te_cnt,
		flex_cnt = excluded.flex_cnt,
		sf_cnt = excluded.sf_cnt,
		starter_cnt = excluded.starter_cnt,
		total_roster_cnt = excluded.total_roster_cnt,
		sport = excluded.sport,
      	insert_date = excluded.insert_date,
        rf_cnt = excluded.rf_cnt,
        league_cat = excluded.league_cat,
        league_year = excluded.league_year;
    """,
        tuple(
            [
                (
                    session_id,
                    user_id,
                    user_name,
                    league[1],
                    league[0],
                    league[2],
                    league[3],
                    league[4],
                    league[5],
                    league[6],
                    league[7],
                    league[8],
                    league[9],
                    league[10],
                    league[11],
                    league[12],
                    entry_time,
                    league[13],
                    league[14],
                    league[15],
                )
                for league in iter(leagues)
            ]
        ),
        page_size=1000,
    )
    db.commit()
    cursor.close()
    return


def player_manager_upates(
    db, button: str, session_id: str, user_id: str, league_id: str
):
    print("Button", button)
    if button in ["trade_tracker", "trade_tracker_fc"]:
        try:
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)

            # delete traded players and picks
            clean_player_trades(db, league_id)
            clean_draft_trades(db, league_id)
            # get trades
            trades = get_trades(league_id, get_sleeper_state())
            # insert trades draft Positions
            draft_positions(db, league_id, user_id)
            insert_trades(db, trades, league_id)
        except:
            return redirect(
                url_for(
                    "leagues.index",
                    error_message="Issue processing trades for that league please contact @superlfex_app for support.",
                )
            )

    else:
        try:
            clean_league_managers(db, league_id)
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, league_id)
            clean_draft_positions(db, league_id)

            managers = get_managers(league_id)
            insert_managers(db, managers)

            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)
        except:
            return redirect(
                url_for(
                    "leagues.index",
                    error_message="Issue processing this league please contact @superlfex_app for support.",
                )
            )


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


league_ids = []
league_metas = []
players = []
current_year = datetime.now().strftime("%Y")

# START ROUTES
@bp.route(
    "/team_view/<string:view_source>/<string:session_id>/<string:league_id>/<string:user_id>/",
    methods=["GET", "POST"],
)
def team_view(user_id, league_id, session_id, view_source):
    db = pg_db()
    if request.method == "POST":
        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )
    source_mapping = {
        "get_league_ktc": {
            "table": "get_league_ktc",
            "max": 12000,
            "rankings": "KeepTradeCut",
        },
        "get_league_fc": {
            "table": "get_league_fc",
            "max": 12000,
            "rankings": "FantasyCalc",
        },
        "get_league_dp": {
            "table": "get_league_dp",
            "max": 12000,
            "rankings": "DynastyProcess",
        },
    }
    sql_view_table = source_mapping[view_source]["table"]
    rankings_source = source_mapping[view_source]["rankings"]

    league_type = get_league_type(league_id)

    if sql_view_table == "get_league_ktc":
        positional_type = (
            "sf_positional_rank" if league_type == "sf_value" else "positional_rank"
        )
        total_rank_type = "sf_rank" if league_type == "sf_value" else "rank"
        league_type = league_type

    elif sql_view_table == "get_league_fc":
        positional_type = (
            "sf_position_rank" if league_type == "sf_value" else "one_qb_position_rank"
        )
        total_rank_type = (
            "sf_overall_rank" if league_type == "sf_value" else "one_qb_overall_rank"
        )
        league_type = league_type

    elif sql_view_table == "get_league_dp":
        positional_type = ""
        total_rank_type = (
            "sf_rank_ecr" if league_type == "sf_value" else "one_qb_rank_ecr"
        )
        league_type = league_type

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "team_views" / f"{sql_view_table}.sql", "r"
    ) as sql_file:
        sql = (
            sql_file.read()
            .replace("'session_id'", f"'{session_id}'")
            .replace("'league_id'", f"'{league_id}'")
            .replace("'user_id'", f"'{user_id}'")
            .replace("sf_value", f"{league_type}")
            .replace("sf_positional_rank", f"{positional_type}")
            .replace("sf_rank ", f"{total_rank_type}")
            .replace("sf_position_rank", f"{positional_type}")
            .replace("sf_rank_ecr", f"{total_rank_type}")
        )
    cursor.execute(sql)
    players = cursor.fetchall()

    position_players = {
        "qb": [i for i in players if i["player_position"] == "QB"],
        "rb": [i for i in players if i["player_position"] == "RB"],
        "wr": [i for i in players if i["player_position"] == "WR"],
        "te": [i for i in players if i["player_position"] == "TE"],
        "picks": [i for i in players if i["player_position"] == "PICKS"],
    }

    qb_graph = {
        "qb_names": [qb["full_name"] for qb in position_players["qb"]],
        "qb_values": [qb["player_value"] for qb in position_players["qb"]],
    }
    rb_graph = {
        "rb_names": [rb["full_name"] for rb in position_players["rb"]],
        "rb_values": [rb["player_value"] for rb in position_players["rb"]],
    }
    wr_graph = {
        "wr_names": [wr["full_name"] for wr in position_players["wr"]],
        "wr_values": [wr["player_value"] for wr in position_players["wr"]],
    }
    te_graph = {
        "te_names": [te["full_name"] for te in position_players["te"]],
        "te_values": [te["player_value"] for te in position_players["te"]],
    }

    ap_players = render_players(players, "power")

    owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "team_views" / "get_league_ktc_summary.sql",
        "r",
    ) as sql_file:
        sql = (
            sql_file.read()
            .replace("'session_id'", f"'{session_id}'")
            .replace("'league_id'", f"'{league_id}'")
            .replace("'user_id'", f"'{user_id}'")
            .replace("league_type", f"{league_type}")
        )
    owner_cursor.execute(sql)
    owner = owner_cursor.fetchall()

    qbs = [player for player in players if player["player_position"] == "QB"]
    rbs = [player for player in players if player["player_position"] == "RB"]
    wrs = [player for player in players if player["player_position"] == "WR"]
    tes = [player for player in players if player["player_position"] == "TE"]

    qb_scatter = []
    rb_scatter = []
    wr_scatter = []
    te_scatter = []

    for i in qbs:
        qb_scatter.append(
            {"x": i["age"], "y": i["player_value"], "player_name": i["full_name"]}
        )
    for i in rbs:
        rb_scatter.append(
            {"x": i["age"], "y": i["player_value"], "player_name": i["full_name"]}
        )
    for i in wrs:
        wr_scatter.append(
            {"x": i["age"], "y": i["player_value"], "player_name": i["full_name"]}
        )
    for i in tes:
        te_scatter.append(
            {"x": i["age"], "y": i["player_value"], "player_name": i["full_name"]}
        )

    league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    league_cursor.execute(
        f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
    )
    leagues = league_cursor.fetchall()

    avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    avatar_cursor.execute(
        f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
    )
    avatar = avatar_cursor.fetchall()

    league_cursor.close()
    cursor.close()
    avatar_cursor.close()

    return render_template(
        "leagues/team_view.html",
        user_id=user_id,
        league_id=league_id,
        session_id=session_id,
        view_source=view_source,
        owners=owner,
        leagues=leagues,
        league_name=get_league_name(league_id),
        user_name=get_user_name(user_id)[1],
        rankings_source=rankings_source,
        position_players=position_players,
        players=players,
        avatar=avatar,
        qb_graph=qb_graph,
        rb_graph=rb_graph,
        wr_graph=wr_graph,
        te_graph=te_graph,
        ap_players=ap_players,
        qb_scatter=qb_scatter,
        rb_scatter=rb_scatter,
        wr_scatter=wr_scatter,
        te_scatter=te_scatter,
    )


@bp.route("/faqs", methods=["GET"])
def faqs():
    return render_template("leagues/faqs.html")


@bp.route("/", methods=("GET", "POST"))
def index():
    session["session_id"] = session.get("session_id", str(uuid.uuid4()))
    entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    db = pg_db()

    cursor = db.cursor()
    query = f"""INSERT INTO dynastr.user_meta (session_id, ip_address, agent, host, referrer, insert_date) VALUES (%s,%s,%s,%s,%s,%s)"""
    user_meta = (
        str(session.get("session_id", "")),
        str(request.headers.get("X-Real-IP")),
        str(request.headers.get("User-Agent", "")),
        str(request.headers.get("Host", "")),
        str(request.referrer),
        entry_time,
    )
    cursor.execute(query, user_meta)

    if request.method == "GET" and "user_id" in session:
        user_name = get_user_name(session["user_id"])
        return render_template("leagues/index.html", user_name=user_name)
    if request.method == "POST":
        if is_user(request.form["username"]):
            session_id = session.get("session_id", str(uuid.uuid4()))
            user_name = request.form["username"]
            year_ = request.form.get("league_year", "2022")
            session["league_year"] = year_
            user_id = session["user_id"] = get_user_id(user_name)
            leagues = user_leagues(str(user_id), str(year_))
            entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

            insert_current_leagues(
                db, session_id, user_id, user_name, entry_time, leagues
            )
        else:
            return render_template(
                "leagues/index.html",
                error_message="Username not found. Please enter a valid sleeper username.",
            )

        return redirect(url_for("leagues.select_league", year="2022"))

    return render_template("leagues/index.html")


@bp.route("/select_league", methods=["GET", "POST"])
def select_league():
    db = pg_db()

    if request.method == "GET" and session.get("session_id", "No_user") == "No_user":
        return redirect(url_for("leagues.index"))
    try:
        session_id = session.get("session_id", str(uuid.uuid4()))
        user_id = session["user_id"]
        session_year = session["league_year"]

        if request.method == "POST":
            button = list(request.form)[0]
            league_data = eval(request.form[button])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            player_manager_upates(db, button, session_id, user_id, league_id)
            return redirect(
                url_for(
                    f"leagues.{button}",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
    except:
        return redirect(url_for("leagues.index"))

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat  from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_year = '{str(session_year)}'"
    )

    leagues = cursor.fetchall()
    cursor.close()

    ls_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    ls_cursor.execute(
        f"""select 
            league_year
            , count(*) FILTER (WHERE league_cat = 0) as keeper
            , count(*) FILTER (WHERE league_cat = 1) as redraft
            , count(*) FILTER (WHERE league_cat = 2) as dynasty
            , count(*) FILTER (WHERE total_rosters = 8) as eight_team
            , count(*) FILTER (WHERE total_rosters = 10) as ten_team
            , count(*) FILTER (WHERE total_rosters = 12) as twelve_team
            , count(*) FILTER (WHERE total_rosters = 16) as sixteen_team
            , count(*) FILTER (WHERE total_rosters = 32) as thirtytwo_team
            , sum(sf_cnt) as superflex
            , (select count(*) from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_year = '{str(session_year)}') - sum(sf_cnt) as single_qb 
            from dynastr.current_leagues 
            where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_year = '{str(session_year)}'
            group by
            league_year"""
    )
    league_summary = ls_cursor.fetchall()[0]
    ls_cursor.close()


    if len(leagues) > 0:
        return render_template(
            "leagues/select_league.html", leagues=leagues, league_summary=league_summary
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_fp", methods=("GET", "POST"))
def get_league_fp():
    db = pg_db()

    if request.method == "POST":
        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)
        lt = "sf" if league_type == "sf_value" else "one_qb"

        fp_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "get_league_fp.sql", "r"
        ) as sql_file:
            sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("lt_rank_ecr", f"{lt}_rank_ecr")
            )
        fp_cursor.execute(sql)
        fp_players = fp_cursor.fetchall()

        if len(fp_players) < 1:
            return redirect(url_for("leagues.index"))

        fp_team_spots = render_players(fp_players, "contender")

        fp_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "get_league_fp.sql", "r"
        ) as sql_file:
            summary_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("lt_rank_ecr", f"{lt}_rank_ecr")
            )
        fp_owners_cursor.execute(summary_sql)
        fp_owners = fp_owners_cursor.fetchall()
        page_user = [
            (
                i["display_name"],
                i["qb_avg_rank"],
                i["rb_avg_rank"],
                i["wr_avg_rank"],
                i["te_avg_rank"],
                i["starters_avg_rank"],
                i["bench_avg_rank"],
            )
            for i in fp_owners
            if i["user_id"] == user_id
        ]

        try:
            labels = [row["display_name"] for row in fp_owners]
            values = [row["total_avg"] for row in fp_owners]
            total_value = [int(row["total_avg"]) for row in fp_owners][0] * 0.95

            pct_values = [
                100 - abs((total_value / int(row["total_avg"])) - 1) * 100
                for row in fp_owners
            ]
        except:
            pct_values = []

        fp_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "fp_ba.sql", "r"
        ) as sql_file:
            ba_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("lt_rank_ecr", f"{lt}_rank_ecr")
            )
        fp_ba_cursor.execute(ba_sql)
        fp_ba = fp_ba_cursor.fetchall()
        fp_ba_qb = [player for player in fp_ba if player["player_position"] == "QB"]
        fp_ba_rb = [player for player in fp_ba if player["player_position"] == "RB"]
        fp_ba_wr = [player for player in fp_ba if player["player_position"] == "WR"]
        fp_ba_te = [player for player in fp_ba if player["player_position"] == "TE"]
        fp_best_available = {
            "QB": fp_ba_qb,
            "RB": fp_ba_rb,
            "WR": fp_ba_wr,
            "TE": fp_ba_te,
        }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute(
            "select max(insert_date) from dynastr.espn_player_projections"
        )
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        total_rosters = get_league_rosters_size(league_id)
        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        fp_owners_cursor.close()
        fp_cursor.close()
        date_cursor.close()
        fp_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league_fp.html",
            owners=fp_owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=fp_team_spots,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=fp_best_available,
            avatar=avatar,
        )


@bp.route("/get_league", methods=("GET", "POST"))
def get_league():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)
        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "get_league.sql", "r"
        ) as get_league_detail_file:
            get_league_detail_sql = (
                get_league_detail_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        player_cursor.execute(get_league_detail_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "get_league.sql", "r"
        ) as get_league_summary_file:
            get_league_summary_sql = (
                get_league_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        owner_cursor.execute(get_league_summary_sql)
        owners = owner_cursor.fetchall()
        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["picks_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in owners
            if i["user_id"] == user_id
        ]

        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            total_value = [row["total_value"] for row in owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
        except:
            pct_values = []

        ktc_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "ktc_ba.sql", "r"
        ) as sql_file:
            ktc_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        ktc_ba_cursor.execute(ktc_sql)
        ba = ktc_ba_cursor.fetchall()

        ba_qb = [player for player in ba if player["player_position"] == "QB"]
        ba_rb = [player for player in ba if player["player_position"] == "RB"]
        ba_wr = [player for player in ba if player["player_position"] == "WR"]
        ba_te = [player for player in ba if player["player_position"] == "TE"]
        best_available = {"QB": ba_qb, "RB": ba_rb, "WR": ba_wr, "TE": ba_te}

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.ktc_player_ranks")
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        total_rosters = int(get_league_rosters_size(league_id))

        team_spots = render_players(players, "power")

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        owner_cursor.close()
        player_cursor.close()
        ktc_ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league.html",
            owners=owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=team_spots,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_fc", methods=("GET", "POST"))
def get_league_fc():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)

        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "get_league_fc.sql", "r"
        ) as get_league_detail_file:
            get_league_detail_sql = (
                get_league_detail_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        player_cursor.execute(get_league_detail_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "get_league_fc.sql", "r"
        ) as get_league_summary_file:
            get_league_summary_sql = (
                get_league_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        owner_cursor.execute(get_league_summary_sql)
        owners = owner_cursor.fetchall()
        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["picks_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in owners
            if i["user_id"] == user_id
        ]

        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            total_value = [row["total_value"] for row in owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
        except:
            pct_values = []

        ktc_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "fc_ba.sql", "r"
        ) as sql_file:
            ktc_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        ktc_ba_cursor.execute(ktc_sql)
        ba = ktc_ba_cursor.fetchall()

        ba_qb = [player for player in ba if player["player_position"] == "QB"]
        ba_rb = [player for player in ba if player["player_position"] == "RB"]
        ba_wr = [player for player in ba if player["player_position"] == "WR"]
        ba_te = [player for player in ba if player["player_position"] == "TE"]
        best_available = {"QB": ba_qb, "RB": ba_rb, "WR": ba_wr, "TE": ba_te}

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.ktc_player_ranks")
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        total_rosters = int(get_league_rosters_size(league_id))

        team_spots = render_players(players, "power")

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        owner_cursor.close()
        player_cursor.close()
        ktc_ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league_fc.html",
            owners=owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=team_spots,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_dp", methods=("GET", "POST"))
def get_league_dp():
    db = pg_db()
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)

        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "get_league_dp.sql", "r"
        ) as get_league_dp_details_file:
            get_league_dp_details_sql = (
                get_league_dp_details_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        player_cursor.execute(get_league_dp_details_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        team_spots = render_players(players, "power")

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "get_league_dp.sql", "r"
        ) as get_league_dp_summary_file:
            get_league_dp_summary_sql = (
                get_league_dp_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        owner_cursor.execute(get_league_dp_summary_sql)
        owners = owner_cursor.fetchall()
        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["picks_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in owners
            if i["user_id"] == user_id
        ]
        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            total_value = [row["total_value"] for row in owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
        except:
            pct_values = []

        ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "dp_ba.sql", "r"
        ) as sql_file:
            dp_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        ba_cursor.execute(dp_sql)
        ba = ba_cursor.fetchall()

        ba_qb = [player for player in ba if player["player_position"] == "QB"]
        ba_rb = [player for player in ba if player["player_position"] == "RB"]
        ba_wr = [player for player in ba if player["player_position"] == "WR"]
        ba_te = [player for player in ba if player["player_position"] == "TE"]
        best_available = {"QB": ba_qb, "RB": ba_rb, "WR": ba_wr, "TE": ba_te}

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.dp_player_ranks")
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        total_rosters = get_league_rosters_size(league_id)

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        owner_cursor.close()
        player_cursor.close()
        ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league_dp.html",
            owners=owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=team_spots,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/trade_tracker", methods=["GET", "POST"])
def trade_tracker():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)
        print("LEAGUE_TYPE", league_type)
        trades_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "trade_tracker.sql", "r"
        ) as trade_tracker_details_file:
            trade_tracker_details_sql = (
                trade_tracker_details_file.read()
                .replace("'current_year'", f"'{current_year}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        trades_cursor.execute(trade_tracker_details_sql)

        analytics_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "trade_tracker.sql", "r"
        ) as trade_tracker_summary_file:
            trade_tracker_summary_sql = (
                trade_tracker_summary_file.read()
                .replace("'current_year'", f"'{current_year}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        analytics_cursor.execute(trade_tracker_summary_sql)

        trades = trades_cursor.fetchall()
        summary_table = analytics_cursor.fetchall()
        transaction_ids = list(
            set([(i["transaction_id"], i["status_updated"]) for i in trades])
        )
        transaction_ids = sorted(
            transaction_ids,
            key=lambda x: datetime.utcfromtimestamp(int(str(x[-1])[:10])),
            reverse=True,
        )
        managers_list = list(
            set([(i["display_name"], i["transaction_id"]) for i in trades])
        )
        trades_dict = {}
        for transaction_id in transaction_ids:
            trades_dict[transaction_id[0]] = {
                i[0]: [p for p in trades if p["display_name"] == i[0]]
                for i in managers_list
                if i[1] == transaction_id[0]
            }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.ktc_player_ranks")
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        return render_template(
            "leagues/trade_tracker.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            league_name=get_league_name(league_id),
        )


@bp.route("/trade_tracker_fc", methods=["GET", "POST"])
def trade_tracker_fc():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)
        print("LEAGUE_TYPE", league_type)
        trades_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "trade_tracker_fc.sql", "r"
        ) as trade_tracker_fc_details_file:
            trade_tracker_fc_details_sql = (
                trade_tracker_fc_details_file.read()
                .replace("'current_year'", f"'{current_year}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        trades_cursor.execute(trade_tracker_fc_details_sql)

        analytics_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "trade_tracker_fc.sql", "r"
        ) as trade_tracker_summary_file:
            trade_tracker_summary_sql = (
                trade_tracker_summary_file.read()
                .replace("'current_year'", f"'{current_year}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        analytics_cursor.execute(trade_tracker_summary_sql)

        trades = trades_cursor.fetchall()
        summary_table = analytics_cursor.fetchall()
        transaction_ids = list(
            set([(i["transaction_id"], i["status_updated"]) for i in trades])
        )
        transaction_ids = sorted(
            transaction_ids,
            key=lambda x: datetime.utcfromtimestamp(int(str(x[-1])[:10])),
            reverse=True,
        )
        managers_list = list(
            set([(i["display_name"], i["transaction_id"]) for i in trades])
        )
        trades_dict = {}
        for transaction_id in transaction_ids:
            trades_dict[transaction_id[0]] = {
                i[0]: [p for p in trades if p["display_name"] == i[0]]
                for i in managers_list
                if i[1] == transaction_id[0]
            }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.fc_player_ranks")
        _date = date_cursor.fetchall()
        fc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round((current_time - fc_max_time).total_seconds() / 60.0)

        return render_template(
            "leagues/trade_tracker_fc.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            league_name=get_league_name(league_id),
        )


@bp.route("/contender_rankings", methods=["GET", "POST"])
def contender_rankings():
    db = pg_db()
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")

        contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "contender_rankings.sql", "r"
        ) as contender_rankings_details_file:
            contender_rankings_details_sql = (
                contender_rankings_details_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        contenders_cursor.execute(contender_rankings_details_sql)
        contenders = contenders_cursor.fetchall()
        if len(contenders) < 1:
            return redirect(url_for("leagues.index"))

        c_aps = render_players(contenders, "contender")

        c_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "contender_rankings.sql", "r"
        ) as contender_rankings_summary_file:
            contender_rankings_summary_sql = (
                contender_rankings_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        c_owners_cursor.execute(contender_rankings_summary_sql)
        c_owners = c_owners_cursor.fetchall()

        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in c_owners
            if i["user_id"] == user_id
        ]
        try:
            labels = [row["display_name"] for row in c_owners]
            values = [row["total_value"] for row in c_owners]
            total_value = [row["total_value"] for row in c_owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in c_owners
            ]
        except:
            pct_values = []

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "con_espn_ba.sql", "r"
        ) as sql_file:
            con_espn_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        con_ba_cursor.execute(con_espn_sql)
        con_ba = con_ba_cursor.fetchall()

        con_ba_qb = [player for player in con_ba if player["player_position"] == "QB"]
        con_ba_rb = [player for player in con_ba if player["player_position"] == "RB"]
        con_ba_wr = [player for player in con_ba if player["player_position"] == "WR"]
        con_ba_te = [player for player in con_ba if player["player_position"] == "TE"]
        con_best_available = {
            "QB": con_ba_qb,
            "RB": con_ba_rb,
            "WR": con_ba_wr,
            "TE": con_ba_te,
        }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute(
            "select max(insert_date) from dynastr.espn_player_projections"
        )
        _date = date_cursor.fetchall()
        ktc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - ktc_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        contenders_cursor.close()
        c_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings.html",
            owners=c_owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            aps=c_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=con_best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_fc", methods=["GET", "POST"])
def fc_contender_rankings():
    db = pg_db()
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        league_type = get_league_type(league_id)
        fc_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "contender_rankings_fc.sql",
            "r",
        ) as contender_rankings_fc_details_file:
            contender_rankings_fc_details_sql = (
                contender_rankings_fc_details_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        fc_contenders_cursor.execute(contender_rankings_fc_details_sql)
        contenders = fc_contenders_cursor.fetchall()
        if len(contenders) < 1:
            return redirect(url_for("leagues.index"))

        fc_aps = render_players(contenders, "contender")

        fc_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "contender_rankings_fc.sql",
            "r",
        ) as contender_rankings_fc_summary_file:
            contender_rankings_fc_summary_sql = (
                contender_rankings_fc_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        fc_owners_cursor.execute(contender_rankings_fc_summary_sql)

        fc_owners = fc_owners_cursor.fetchall()

        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in fc_owners
            if i["user_id"] == user_id
        ]
        try:
            labels = [row["display_name"] for row in fc_owners]
            values = [row["total_value"] for row in fc_owners]
            total_value = [row["total_value"] for row in fc_owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in fc_owners
            ]
        except:
            pct_values = []

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "con_fc_ba.sql", "r"
        ) as sql_file:
            con_fc_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        con_ba_cursor.execute(con_fc_sql)
        con_ba = con_ba_cursor.fetchall()

        con_ba_qb = [player for player in con_ba if player["player_position"] == "QB"]
        con_ba_rb = [player for player in con_ba if player["player_position"] == "RB"]
        con_ba_wr = [player for player in con_ba if player["player_position"] == "WR"]
        con_ba_te = [player for player in con_ba if player["player_position"] == "TE"]
        con_best_available = {
            "QB": con_ba_qb,
            "RB": con_ba_rb,
            "WR": con_ba_wr,
            "TE": con_ba_te,
        }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.fp_player_ranks")
        _date = date_cursor.fetchall()
        nfl_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - nfl_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        fc_contenders_cursor.close()
        fc_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings_fc.html",
            owners=fc_owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            aps=fc_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=con_best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_nfl", methods=["GET", "POST"])
def nfl_contender_rankings():
    db = pg_db()
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        nfl_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "contender_rankings_nfl.sql",
            "r",
        ) as contender_rankings_nfl_details_file:
            contender_rankings_nfl_details_sql = (
                contender_rankings_nfl_details_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        nfl_contenders_cursor.execute(contender_rankings_nfl_details_sql)
        contenders = nfl_contenders_cursor.fetchall()
        if len(contenders) < 1:
            return redirect(url_for("leagues.index"))

        nfl_aps = render_players(contenders, "contender")

        nfl_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "contender_rankings_nfl.sql",
            "r",
        ) as contender_rankings_nfl_summary_file:
            contender_rankings_nfl_summary_sql = (
                contender_rankings_nfl_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        nfl_owners_cursor.execute(contender_rankings_nfl_summary_sql)

        nfl_owners = nfl_owners_cursor.fetchall()

        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in nfl_owners
            if i["user_id"] == user_id
        ]
        try:
            labels = [row["display_name"] for row in nfl_owners]
            values = [row["total_value"] for row in nfl_owners]
            total_value = [row["total_value"] for row in nfl_owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in nfl_owners
            ]
        except:
            pct_values = []

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "con_nfl_ba.sql", "r"
        ) as sql_file:
            con_nfl_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        con_ba_cursor.execute(con_nfl_sql)
        con_ba = con_ba_cursor.fetchall()

        con_ba_qb = [player for player in con_ba if player["player_position"] == "QB"]
        con_ba_rb = [player for player in con_ba if player["player_position"] == "RB"]
        con_ba_wr = [player for player in con_ba if player["player_position"] == "WR"]
        con_ba_te = [player for player in con_ba if player["player_position"] == "TE"]
        con_best_available = {
            "QB": con_ba_qb,
            "RB": con_ba_rb,
            "WR": con_ba_wr,
            "TE": con_ba_te,
        }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute(
            "select max(insert_date) from dynastr.nfl_player_projections"
        )
        _date = date_cursor.fetchall()
        nfl_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round(
            (current_time - nfl_max_time).total_seconds() / 60.0
        )

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        nfl_contenders_cursor.close()
        nfl_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings_nfl.html",
            owners=nfl_owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            aps=nfl_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=con_best_available,
            avatar=avatar,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_fp", methods=["GET", "POST"])
def fp_contender_rankings():
    db = pg_db()
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        player_manager_upates(db, button, session_id, user_id, league_id)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        fp_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "contender_rankings_fp.sql",
            "r",
        ) as contender_rankings_fp_details_file:
            contender_rankings_fp_details_sql = (
                contender_rankings_fp_details_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        fp_contenders_cursor.execute(contender_rankings_fp_details_sql)
        contenders = fp_contenders_cursor.fetchall()

        if len(contenders) < 1:
            return redirect(url_for("leagues.index"))

        fp_aps = render_players(contenders, "contender")

        fp_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "contender_rankings_fp.sql",
            "r",
        ) as contender_rankings_fp_summary_file:
            contender_rankings_fp_summary_sql = (
                contender_rankings_fp_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        fp_owners_cursor.execute(contender_rankings_fp_summary_sql)

        fp_owners = fp_owners_cursor.fetchall()

        page_user = [
            (
                i["display_name"],
                i["qb_rank"],
                i["rb_rank"],
                i["wr_rank"],
                i["te_rank"],
                i["starters_rank"],
                i["bench_rank"],
            )
            for i in fp_owners
            if i["user_id"] == user_id
        ]

        try:
            labels = [row["display_name"] for row in fp_owners]
            values = [row["total_value"] for row in fp_owners]
            total_value = [row["total_value"] for row in fp_owners][0] * 1.05
            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in fp_owners
            ]
        except:
            pct_values = []

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "con_fp_ba.sql", "r"
        ) as sql_file:
            con_fp_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        con_ba_cursor.execute(con_fp_sql)
        con_ba = con_ba_cursor.fetchall()

        con_ba_qb = [player for player in con_ba if player["player_position"] == "QB"]
        con_ba_rb = [player for player in con_ba if player["player_position"] == "RB"]
        con_ba_wr = [player for player in con_ba if player["player_position"] == "WR"]
        con_ba_te = [player for player in con_ba if player["player_position"] == "TE"]
        con_best_available = {
            "QB": con_ba_qb,
            "RB": con_ba_rb,
            "WR": con_ba_wr,
            "TE": con_ba_te,
        }

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute(
            "select max(insert_date) from dynastr.fp_player_projections"
        )
        _date = date_cursor.fetchall()
        fp_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round((current_time - fp_max_time).total_seconds() / 60.0)

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        nfl_current_week = get_sleeper_state()["leg"]
        total_rosters = get_league_rosters_size(league_id)

        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        fp_contenders_cursor.close()
        fp_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings_fp.html",
            owners=fp_owners,
            page_user=page_user,
            total_rosters=total_rosters,
            users=users,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            aps=fp_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            update_diff_minutes=update_diff_minutes,
            labels=labels,
            values=values,
            pct_values=pct_values,
            best_available=con_best_available,
            avatar=avatar,
            nfl_current_week=nfl_current_week,
        )
    else:
        return redirect(url_for("leagues.index"))
