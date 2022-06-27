import requests, uuid
import psycopg2
from psycopg2.extras import execute_batch, execute_values

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

from pathlib import Path
from datetime import datetime

from superflex.db import get_db, pg_db

bp = Blueprint("leagues", __name__, url_prefix="/")
bp.secret_key = "hello"


def n_user_id(user_name: str) -> str:
    user_url = f"https://api.sleeper.app/v1/user/{user_name}"
    un_res = requests.get(user_url)
    user_id = un_res.json()["user_id"]
    return user_id


def user_leagues(user_name: str, year=datetime.now().strftime("%Y")) -> list:
    owner_id = n_user_id(user_name)
    leagues_url = f"https://api.sleeper.app/v1/user/{owner_id}/leagues/nfl/{year}"
    leagues_res = requests.get(leagues_url)
    leagues = []
    for league in leagues_res.json():
        qbs = len([i for i in league["roster_positions"] if i == "QB"])
        rbs = len([i for i in league["roster_positions"] if i == "RB"])
        wrs = len([i for i in league["roster_positions"] if i == "WR"])
        tes = len([i for i in league["roster_positions"] if i == "TE"])
        flexes = len([i for i in league["roster_positions"] if i == "FLEX"])
        super_flexes = len([i for i in league["roster_positions"] if i == "SUPER_FLEX"])
        starters = sum([qbs, rbs, wrs, tes, flexes, super_flexes])
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


def get_user_name(user_id: str) -> str:
    user_req = requests.get(f"https://api.sleeper.app/v1/user/{user_id}")
    user_meta = user_req.json()
    return (user_meta["username"], user_meta["display_name"])


def get_user_id(user_name: str) -> str:
    user_id_req = requests.get(f"https://api.sleeper.app/v1/user/{user_name}")
    return user_id_req.json()["user_id"]


def get_league_name(league_id: str) -> str:
    league_req = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    return league_req.json()["name"]


def get_league_names(user_id, year: str = "2022"):
    leagues_res = requests.get(
        f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{year}"
    )
    return [(i["name"], i["league_id"]) for i in leagues_res.json()]


def get_users_data(league_id):
    users_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    return [
        (user_meta["display_name"], user_meta["user_id"])
        for user_meta in users_res.json()
    ]


def get_league_type(league_id: str) -> str:
    league_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    return (
        "sf_value"
        if "SUPER_FLEX" in league_res.json()["roster_positions"]
        else "one_qb_value"
    )


def get_league_rosters_size(league_id: str) -> int:
    league_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    return league_res.json()["total_rosters"]


def delete_players(session_id, league_id, user_id):
    db = get_db()
    query = f"""
    DELETE from owned_players where session_id = '{str(session_id)}' and owner_user_id = '{str(user_id)}' and owner_league_id = '{str(league_id)}'
    """
    db.execute(query)
    db.commit()
    print(f"DELETE CALLED:{session_id,user_id,league_id}")


def get_league_rosters(league_id: str) -> list:
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    return rosters.json()


def get_traded_picks(league_id: str) -> list:
    total_res = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/traded_picks"
    )
    return total_res.json()


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


def insert_managers(db, managers: list) -> None:
    with db.cursor() as cursor:
        execute_values(
            cursor,
            """
                INSERT INTO dynastr.managers VALUES %s
                ON CONFLICT (user_id)
                DO UPDATE SET source = EXCLUDED.source
	                        , league_id = EXCLUDED.league_id
                            , avatar = EXCLUDED.avatar
                            , display_name = EXCLUDED.display_name;;
                """,
            [
                (manager[0], manager[1], manager[2], manager[3], manager[4])
                for manager in iter(managers)
            ],
            page_size=1000,
        )
    # cursor = db.cursor()
    # execute_batch(cursor, """INSERT INTO dynastr.managers (source, user_id, league_id, avatar, display_name)
    # VALUES (%s, %s, %s, %s, %s)
    # ON CONFLICT (user_id)
    # DO UPDATE SET source = EXCLUDED.source
    #     , league_id = EXCLUDED.league_id
    #     , avatar = EXCLUDED.avatar
    #     , display_name = EXCLUDED.display_name;
    # """, tuple(managers), page_size=1000)
    # db.commit()
    # cursor.close()
    return


def is_user(user_name: str) -> bool:
    res = requests.get(f"https://api.sleeper.app/v1/user/{user_name}")
    return True if res.text != "null" else False


def round_suffix(rank: int) -> str:
    ith = {1: "st", 2: "nd", 3: "rd"}.get(
        rank % 10 * (rank % 100 not in [11, 12, 13]), "th"
    )
    return f"{str(rank)}{ith}"


def clean_league_rosters(db, session_id: str, user_id: str, league_id: str) -> None:
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


def clean_league_picks(db, session_id: str, league_id: str) -> None:
    delete_query = f"""DELETE FROM dynastr.draft_picks where session_id = '{session_id}' and league_id = '{league_id}'"""
    cursor = db.cursor()
    cursor.execute(delete_query)
    cursor.close()
    print("Draft pick trades deleted")
    return


def get_sleeper_state():
    return requests.get("https://api.sleeper.app/v1/state/nfl").json()


def get_trades(league_id: str, nfl_state: dict) -> list:

    leg = nfl_state["leg"] if nfl_state["leg"] > 0 else 1
    all_trades = []
    for i in range(1, leg + 1):
        trans_call = requests.get(
            f"https://api.sleeper.app/v1/league/{league_id}/transactions/{leg}"
        ).json()
        all_trades.append(trans_call)
    trades_payload = [p for p in [i for i in trans_call] if p["type"] == "trade"]
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
        for player_id in league_roster:
            league_players.append(
                [
                    session_id,
                    user_id,
                    player_id,
                    roster["league_id"],
                    roster["owner_id"],
                    entry_time,
                ]
            )
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

            # cursor = db.cursor()
            # execute_batch(cursor, """INSERT INTO dynastr.draft_picks (year, round, round_name, roster_id,owner_id, league_id,draft_id, session_id)
            # VALUES (%s, %s, %s, %s, %s, %s,%s,%s)
            # ON CONFLICT (year, round, roster_id, owner_id, league_id, session_id)
            # DO UPDATE SET round_name = EXCLUDED.round_name
            #     , draft_id = EXCLUDED.draft_id;
            # """, tuple(draft_picks), page_size=1000)
            # db.commit()

    return


def draft_positions(db, league_id: str, user_id: str, draft_order: list = []) -> None:
    draft_id = get_draft_id(league_id)
    draft = get_draft(draft_id["draft_id"])

    season = draft["season"]
    rounds = draft_id["settings"]["rounds"]
    roster_slot = {
        int(k): v for k, v in draft["slot_to_roster_id"].items() if v is not None
    }
    rs_dict = dict(sorted(roster_slot.items(), key=lambda item: int(item[0])))

    try:
        draft_order_dict = dict(
            sorted(draft["draft_order"].items(), key=lambda item: item[1])
        )
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
            ,roster_id = EXCLUDED.roster_id
            , draft_id = EXCLUDED.draft_id
    ;""",
        tuple(draft_order),
        page_size=1000,
    )
    db.commit()
    cursor.close()
    return


league_ids = []
league_metas = []
players = []
current_year = datetime.now().strftime("%Y")
# START ROUTES


@bp.route("/", methods=("GET", "POST"))
def index():
    db = pg_db()
    if request.method == "GET" and "user_id" in session:
        user_name = get_user_name(session["user_id"])
        return render_template("leagues/index.html", user_name=user_name)
    if request.method == "POST" and is_user(request.form["username"]):
        session_id = session["session_id"] = str(uuid.uuid4())
        user_name = request.form["username"]
        user_id = session["user_id"] = get_user_id(user_name)
        leagues = user_leagues(str(user_id))
        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

        with db.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO dynastr.current_leagues VALUES %s;
                """,
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
                    )
                    for league in iter(leagues)
                ],
                page_size=1000,
            )

        return redirect(url_for("leagues.select_league"))
    return render_template("leagues/index.html")


@bp.route("/select_league", methods=["GET", "POST"])
def select_league():
    # db = get_db()
    db = pg_db()
    if request.method == "GET" and session.get("session_id", "No_user") == "No_user":
        return redirect(url_for("leagues.index"))

    session_id = session["session_id"]
    user_id = session["user_id"]

    if request.method == "POST":
        if list(request.form)[0] == "sel_league_data":
            league_data = eval(request.form["sel_league_data"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # delete data players, picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # clean_managers()
            # clean_draft_trades()
            # clean_draft_positions()

            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.get_league",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        elif list(request.form)[0] == "sel_trade_tracker":
            league_data = eval(request.form["sel_trade_tracker"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]

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

            return redirect(
                url_for(
                    "leagues.trade_tracker",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        elif list(request.form)[0] == "sel_contender_rankings":
            league_data = eval(request.form["sel_contender_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]

            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)

            return redirect(
                url_for(
                    "leagues.contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
    cursor = db.cursor()
    cursor.execute(
        f"select * from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}'"
    )
    leagues = cursor.fetchall()
    cursor.close()

    if len(leagues) > 0:
        return render_template("leagues/select_league.html", leagues=leagues)
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_fp", methods=("GET", "POST"))
def get_league_fp():
    db = pg_db()
    date_ = datetime.now().strftime("%m/%d/%Y")
    if request.method == "POST":
        if list(request.form)[0] == "trade_tracker":

            league_data = eval(request.form["trade_tracker"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]

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

            return redirect(
                url_for(
                    "leagues.trade_tracker",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "contender_rankings":
            league_data = eval(request.form["contender_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "ktc_rankings":
            print("paspa")
            print(request.form)
            league_data = eval(request.form["ktc_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league",
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
        lt = "sf_" if league_type == "sf_value" else "one_qb_"
        print("LEAGUE_TYPE", league_type)

        fp_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_cursor.execute(
            f"""select all_players.user_id 
, all_players.display_name 
, all_players.league_id
, all_players.session_id
, all_players.full_name
, all_players.player_id as sleeper_id
, all_players.player_position
, all_players.fantasy_position
, all_players.fantasy_designation
, all_players.team
, all_players.player_value
, sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
from (SELECT
lp.user_id 
, m.display_name 
, lp.league_id
, lp.session_id
, p.full_name as full_name
, p.player_id
, p.player_position
, 'BENCH' as fantasy_position
, 'BENCH' as fantasy_designation
, p.team
, coalesce(fp.sf_rank_ecr, 529) as player_value
from dynastr.league_players lp
inner join dynastr.players p on lp.player_id = p.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(p.first_name, p.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and p.player_position != 'FB'    
and fp.fp_player_id not in (				
					select 
					all_t.fp_player_id
					from (
					select
					t2.user_id
					, t2.display_name
					, t2.league_id
					, t2.session_id
					, t2.full_name
                    , t2.player_id
					, t2.fp_player_id
					, t2.team
					, t2.player_position
					, 'SUPER_FLEX' as fantasy_position
					, t2.player_value
					from 
					(select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, t1.player_value
					, t1.player_order
					, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
					, t1.qb_cnt
					, t1.rb_cnt
					, t1.wr_cnt
					, t1.te_cnt
					, t1.flex_cnt
					, t1.sf_cnt
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
					, qb_cnt
					, rb_cnt
					, wr_cnt
					, te_cnt
					, flex_cnt
					, sf_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
                    and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position IN ('QB','RB', 'WR', 'TE')   
					order by display_name, pl.player_position, player_value asc) t1
					where 1=1
					and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
					order by 
					display_name, player_order asc) t2
					where t2.flex_order <= sf_cnt
					UNION ALL
					select
					t2.user_id
					, t2.display_name
					, t2.league_id
					, t2.session_id
					, t2.full_name
                    , t2.player_id
					, t2.fp_player_id
					, t2.team
					, t2.player_position
					, 'FLEX' as fantasy_position
					, t2.player_value
					from 
					(select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, t1.player_value
					, t1.player_order
					, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
					, t1.qb_cnt
					, t1.rb_cnt
					, t1.wr_cnt
					, t1.te_cnt
					, t1.flex_cnt
					, t1.sf_cnt
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
					, qb_cnt
					, rb_cnt
					, wr_cnt
					, te_cnt
					, flex_cnt
					, sf_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position IN ('RB', 'WR', 'TE')   
					order by display_name, pl.player_position, player_value asc) t1
					where 1=1
					and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
					order by 
					display_name, player_order asc) t2
					where t2.flex_order <= t2.flex_cnt+sf_cnt and t2.flex_order > sf_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'RB' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, rb_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
                    and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'RB'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= rb_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'WR' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, wr_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'            
					and pl.player_position != 'FB'   
					and pl.player_position = 'WR'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= wr_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'TE' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, te_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'            
					and pl.player_position != 'FB'   
					and pl.player_position = 'TE'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= te_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
                    , t1.player_id
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'QB' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
                    , pl.player_id
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, qb_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'QB'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= qb_cnt
					order by display_name, fantasy_position,player_value asc
					) all_t
)
UNION ALL 			
				
select 
all_t.user_id
,all_t.display_name
,all_t.league_id
,all_t.session_id
,all_t.full_name
,all_t.player_id
,all_t.player_position
,all_t.fantasy_position
, 'STARTER' as fantasy_designation
,all_t.team
,all_t.player_value as player_value
--, sum(all_t.player_value) OVER (PARTITION BY all_t.user_id) as total_value  
from (
select
t2.user_id
, t2.display_name
, t2.league_id
, t2.session_id
, t2.full_name
, t2.player_id
, t2.fp_player_id
, t2.team
, t2.player_position
, 'SUPER_FLEX' as fantasy_position
, t2.player_value
from 
(select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, t1.player_value
, t1.player_order
, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
, t1.qb_cnt
, t1.rb_cnt
, t1.wr_cnt
, t1.te_cnt
, t1.flex_cnt
, t1.sf_cnt
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position IN ('QB','RB', 'WR', 'TE')   
order by display_name, pl.player_position, player_value asc) t1
where 1=1
and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
order by 
display_name, player_order asc) t2
where t2.flex_order <= sf_cnt
UNION ALL
select
t2.user_id
, t2.display_name
, t2.league_id
, t2.session_id
, t2.full_name
, t2.player_id
, t2.fp_player_id
, t2.team
, t2.player_position
, 'FLEX' as fantasy_position
, t2.player_value
from 
(select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, t1.player_value
, t1.player_order
, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
, t1.qb_cnt
, t1.rb_cnt
, t1.wr_cnt
, t1.te_cnt
, t1.flex_cnt
, t1.sf_cnt
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position IN ('RB', 'WR', 'TE')   
order by display_name, pl.player_position, player_value asc) t1
where 1=1
and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
order by 
display_name, player_order asc) t2
where t2.flex_order <= t2.flex_cnt+sf_cnt and t2.flex_order > sf_cnt
UNION ALL 
select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, 'RB' as fantasy_position
, t1.player_value
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, rb_cnt
, flex_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position = 'RB'   
order by display_name, pl.player_position, player_value asc) t1
where player_order <= rb_cnt
UNION ALL 
select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, 'WR' as fantasy_position
, t1.player_value
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, wr_cnt
, flex_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position = 'WR'   
order by display_name, pl.player_position, player_value asc) t1
where player_order <= wr_cnt
UNION ALL 
select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, 'TE' as fantasy_position
, t1.player_value
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, te_cnt
, flex_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position = 'TE'   
order by display_name, pl.player_position, player_value asc) t1
where player_order <= te_cnt
UNION ALL 
select 
t1.user_id
, t1.display_name
, t1.league_id
, t1.session_id
, t1.full_name
, t1.player_id
, t1.fp_player_id
, t1.team
, t1.player_position
, 'QB' as fantasy_position
, t1.player_value
from 
(SELECT
lp.user_id
, m.display_name
, lp.league_id
, lp.session_id
, pl.full_name as full_name
, pl.player_id
, fp.fp_player_id
, pl.team
, pl.player_position
, coalesce(fp.sf_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
, qb_cnt
, flex_cnt
from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.managers m on lp.user_id = m.user_id
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
where 1=1
and lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position != 'FB'   
and pl.player_position = 'QB'   
order by display_name, pl.player_position, player_value asc) t1
where player_order <= qb_cnt
order by display_name, fantasy_position,player_value asc
) all_t) all_players  
order by player_value asc
        """
        )
        fp_players = fp_cursor.fetchall()

        qbs = [player for player in fp_players if player["fantasy_position"] == "QB"]
        rbs = [player for player in fp_players if player["fantasy_position"] == "RB"]
        wrs = [player for player in fp_players if player["fantasy_position"] == "WR"]
        tes = [player for player in fp_players if player["fantasy_position"] == "TE"]
        flex = [player for player in fp_players if player["fantasy_position"] == "FLEX"]
        super_flex = [
            player
            for player in fp_players
            if player["fantasy_position"] == "SUPER_FLEX"
        ]
        bench = [
            player for player in fp_players if player["fantasy_position"] == "BENCH"
        ]

        fp_aps = {
            "qb": qbs,
            "rb": rbs,
            "wr": wrs,
            "te": tes,
            "flex": flex,
            "super_flex": super_flex,
            "bench": bench,
        }

        fp_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_owners_cursor.execute(
            f"""SELECT 
                    t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by max(qb_value) asc) qb_rank
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by max(rb_value) asc) rb_rank
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by max(wr_value) asc) wr_rank
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by max(te_value) asc) te_rank
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by max(flex_value) asc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by max(super_flex_value) asc) super_flex_rank
					, max(bench_value) as bench_value
                    , DENSE_RANK() OVER (order by max(bench_value) asc) bench_rank

                    from (select 
                    user_id
                    ,display_name
                    , sum(player_value) as position_value
                    , total_value
                    , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) asc) position_rank
                    , DENSE_RANK() OVER (order by total_value asc) total_rank
                    , fantasy_position
                    , case when fantasy_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                    , case when fantasy_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                    , case when fantasy_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                    , case when fantasy_position = 'TE' THEN sum(player_value) else 0 end as te_value
                    , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                    , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
					, case when fantasy_position = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                    from 
                    (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.league_id
                    , all_players.session_id
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    from (SELECT
                    lp.user_id 
                    , m.display_name 
                    , lp.league_id
                    , lp.session_id
                    , p.full_name as full_name
                    , p.player_position
                    , 'BENCH' as fantasy_position
                    , 'BENCH' as fantasy_designation
                    , p.team
                    , coalesce(fp.sf_rank_ecr, 529) as player_value
                    from dynastr.league_players lp
                    inner join dynastr.players p on lp.player_id = p.player_id
                    LEFT JOIN dynastr.fp_player_ranks fp on concat(p.first_name, p.last_name) = concat(fp.player_first_name, fp.player_last_name)
                    inner join dynastr.managers m on lp.user_id = m.user_id
                    where 1=1
                    and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'        
                    and p.player_position != 'FB'    
                    and fp.fp_player_id not in (		
					select 
					all_t.fp_player_id
					from (
					select
					t2.user_id
					, t2.display_name
					, t2.league_id
					, t2.session_id
					, t2.full_name
					, t2.fp_player_id
					, t2.team
					, t2.player_position
					, 'SUPER_FLEX' as fantasy_position
					, t2.player_value
					from 
					(select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, t1.player_value
					, t1.player_order
					, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
					, t1.qb_cnt
					, t1.rb_cnt
					, t1.wr_cnt
					, t1.te_cnt
					, t1.flex_cnt
					, t1.sf_cnt
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
					, qb_cnt
					, rb_cnt
					, wr_cnt
					, te_cnt
					, flex_cnt
					, sf_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position IN ('QB','RB', 'WR', 'TE')   
					order by display_name, pl.player_position, player_value asc) t1
					where 1=1
					and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
					order by 
					display_name, player_order asc) t2
					where  t2.flex_order <= sf_cnt
					UNION ALL
					select
					t2.user_id
					, t2.display_name
					, t2.league_id
					, t2.session_id
					, t2.full_name
					, t2.fp_player_id
					, t2.team
					, t2.player_position
					, 'FLEX' as fantasy_position
					, t2.player_value
					from 
					(select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, t1.player_value
					, t1.player_order
					, RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
					, t1.qb_cnt
					, t1.rb_cnt
					, t1.wr_cnt
					, t1.te_cnt
					, t1.flex_cnt
					, t1.sf_cnt
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
					, qb_cnt
					, rb_cnt
					, wr_cnt
					, te_cnt
					, flex_cnt
					, sf_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position IN ('RB', 'WR', 'TE')   
					order by display_name, pl.player_position, player_value asc) t1
					where 1=1
					and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
					order by 
					display_name, player_order asc) t2
					where t2.flex_order <= t2.flex_cnt+sf_cnt and t2.flex_order > sf_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'RB' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, rb_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'RB'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= rb_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'WR' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, wr_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'WR'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= wr_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'TE' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, te_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'TE'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= te_cnt
					UNION ALL 
					select 
					t1.user_id
					, t1.display_name
					, t1.league_id
					, t1.session_id
					, t1.full_name
					, t1.fp_player_id
					, t1.team
					, t1.player_position
					, 'QB' as fantasy_position
					, t1.player_value
					from 
					(SELECT
					lp.user_id
					, m.display_name
					, lp.league_id
					, lp.session_id
					, pl.full_name as full_name
					, fp.fp_player_id
					, pl.team
					, pl.player_position
					, coalesce(fp.sf_rank_ecr, 529) as player_value
					, RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
					, qb_cnt
					, flex_cnt
					from dynastr.league_players lp
					inner join dynastr.players pl on lp.player_id = pl.player_id
					LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
					inner join dynastr.managers m on lp.user_id = m.user_id
					inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
					where 1=1
					and lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
					and pl.player_position != 'FB'   
					and pl.player_position = 'QB'   
					order by display_name, pl.player_position, player_value asc) t1
					where player_order <= qb_cnt
					order by display_name, fantasy_position,player_value asc
					) all_t
                        )
                        UNION ALL 			
                                        
                        select 
                        all_t.user_id
                        ,all_t.display_name
                        ,all_t.league_id
                        ,all_t.session_id
                        ,all_t.full_name
                        ,all_t.player_position
                        ,all_t.fantasy_position
                        , 'STARTER' as fantasy_designation
                        ,all_t.team
                        ,all_t.player_value as player_value
                        --, sum(all_t.player_value) OVER (PARTITION BY all_t.user_id) as total_value  
                        from (
                        select
                        t2.user_id
                        , t2.display_name
                        , t2.league_id
                        , t2.session_id
                        , t2.full_name
                        , t2.fp_player_id
                        , t2.team
                        , t2.player_position
                        , 'SUPER_FLEX' as fantasy_position
                        , t2.player_value
                        from 
                        (select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , t1.player_value
                        , t1.player_order
                        , RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
                        , t1.qb_cnt
                        , t1.rb_cnt
                        , t1.wr_cnt
                        , t1.te_cnt
                        , t1.flex_cnt
                        , t1.sf_cnt
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
                        , qb_cnt
                        , rb_cnt
                        , wr_cnt
                        , te_cnt
                        , flex_cnt
                        , sf_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position IN ('QB','RB', 'WR', 'TE')   
                        order by display_name, pl.player_position, player_value asc) t1
                        where 1=1
                        and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
                        order by 
                        display_name, player_order asc) t2
                        where t2.flex_order <= sf_cnt
                        UNION ALL
                        select
                        t2.user_id
                        , t2.display_name
                        , t2.league_id
                        , t2.session_id
                        , t2.full_name
                        , t2.fp_player_id
                        , t2.team
                        , t2.player_position
                        , 'FLEX' as fantasy_position
                        , t2.player_value
                        from 
                        (select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , t1.player_value
                        , t1.player_order
                        , RANK() OVER (PARTITION BY t1.display_name ORDER BY t1.player_order asc) as flex_order
                        , t1.qb_cnt
                        , t1.rb_cnt
                        , t1.wr_cnt
                        , t1.te_cnt
                        , t1.flex_cnt
                        , t1.sf_cnt
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as position_order
                        , qb_cnt
                        , rb_cnt
                        , wr_cnt
                        , te_cnt
                        , flex_cnt
                        , sf_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position IN ('RB', 'WR', 'TE')   
                        order by display_name, pl.player_position, player_value asc) t1
                        where 1=1
                        and position_order > te_cnt and position_order > wr_cnt and position_order > rb_cnt
                        order by 
                        display_name, player_order asc) t2
                        where t2.flex_order <= t2.flex_cnt+sf_cnt and t2.flex_order > sf_cnt
                        UNION ALL 
                        select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , 'RB' as fantasy_position
                        , t1.player_value
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , rb_cnt
                        , flex_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position = 'RB'   
                        order by display_name, pl.player_position, player_value asc) t1
                        where player_order <= rb_cnt
                        UNION ALL 
                        select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , 'WR' as fantasy_position
                        , t1.player_value
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , wr_cnt
                        , flex_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position = 'WR'   
                        order by display_name, pl.player_position, player_value asc) t1
                        where player_order <= wr_cnt
                        UNION ALL 
                        select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , 'TE' as fantasy_position
                        , t1.player_value
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , te_cnt
                        , flex_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position = 'TE'   
                        order by display_name, pl.player_position, player_value asc) t1
                        where player_order <= te_cnt
                        UNION ALL 
                        select 
                        t1.user_id
                        , t1.display_name
                        , t1.league_id
                        , t1.session_id
                        , t1.full_name
                        , t1.fp_player_id
                        , t1.team
                        , t1.player_position
                        , 'QB' as fantasy_position
                        , t1.player_value
                        from 
                        (SELECT
                        lp.user_id
                        , m.display_name
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name as full_name
                        , fp.fp_player_id
                        , pl.team
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY m.display_name, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc)as player_order
                        , qb_cnt
                        , flex_cnt
                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.managers m on lp.user_id = m.user_id
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '5fe01991-c892-46aa-91e5-a79532f395cc'
                        where 1=1
                        and lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position != 'FB'   
                        and pl.player_position = 'QB'   
                        order by display_name, pl.player_position, player_value asc) t1
                        where player_order <= qb_cnt
                        order by display_name, fantasy_position,player_value asc
                        ) all_t) all_players
                        ) t2 
                                            group by 
                    t2.user_id
                    , t2.display_name
                    , t2.total_value
                    , t2.fantasy_position) t3
                    group by 
                    t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    order by
                    total_value asc"""
        )
        fp_owners = fp_owners_cursor.fetchall()

        return render_template(
            "leagues/get_league_fp.html",
            owners=fp_owners,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=fp_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            date_=date_,
        )


@bp.route("/get_league", methods=("GET", "POST"))
def get_league():
    db = pg_db()
    date_ = datetime.now().strftime("%m/%d/%Y")
    print(request.form)
    if request.method == "POST":
        if list(request.form)[0] == "trade_tracker":

            league_data = eval(request.form["trade_tracker"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]

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

            return redirect(
                url_for(
                    "leagues.trade_tracker",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "contender_rankings":
            league_data = eval(request.form["contender_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_rankings":
            print("paspa")
            print(request.form)
            league_data = eval(request.form["fp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_fp",
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
        player_cursor.execute(
            f"""SELECT
                    asset.user_id 
                    , asset.league_id
                    , asset.session_id
                    , asset.year
                    , CASE WHEN asset.year = asset.season THEN asset.full_name
                        ELSE replace(asset.full_name, 'Mid ','') END AS full_name
                    , asset.full_name
                    , asset.player_name
                    , asset.player_position
                    , asset.team
                    , asset.sleeper_id
                    , value   
                    from      
                    (
                    SELECT
                        lp.user_id 
                        , lp.league_id
                        , lp.session_id
                        , null as season
                        , null as year
                        , p.full_name full_name
                        , p.full_name player_name
                        , p.player_position
                        , p.team
                        , p.player_id sleeper_id
                        , coalesce(ktc.{league_type},-1) as value  

                        from dynastr.league_players lp
                        inner join dynastr.players p on lp.player_id = p.player_id
                        LEFT JOIN dynastr.ktc_player_ranks ktc on concat(p.first_name, p.last_name) = concat(ktc.player_first_name, ktc.player_last_name)
                        where 1=1
                        and session_id = '{session_id}'
                        and league_id = '{league_id}'
                        and p.player_position != 'FB'
                    UNION ALL 
                    SELECT 
                    t3.user_id
                    , t3.league_id
                    , t3.session_id
                    , t3.season
                    , t3.year
                    , t3.full_name
                    , t3.player_name
                    , t3.position
                    , t3.team
                    , t3.sleeper_id
                    , coalesce(ktc.{league_type},-1) as value  
                    FROM
                       (SELECT  
                            al.user_id
                            , al.league_id
                            , null as session_id
                            , al.season
                            , al.year 
                            , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                            ELSE al.year|| ' Mid ' || al.round_name END AS full_name
                            , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                            ELSE al.year|| ' Mid ' || al.round_name END AS player_name 
                            , 'PICKS' as position
                            , null as team
                            , null as sleeper_id
                            FROM (                           
                                SELECT dp.roster_id, dp.year, dp.round_name, dp.league_id, dpos.user_id, dpos.season
                                FROM dynastr.draft_picks dp
                                inner join dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id  

                                where 1=1
                                and dp.league_id = '{league_id}'
                                and dpos.league_id = '{league_id}'
                                and dp.session_id = '{session_id}'
                                ) al 
                            inner join dynastr.draft_positions dname on  dname.roster_id = al.roster_id
                            where 1=1 
                            and dname.league_id = '{league_id}'
                            ) t3
                    LEFT JOIN dynastr.ktc_player_ranks ktc on t3.player_name = ktc.player_full_name
                    ) asset  
                ORDER BY asset.user_id, asset.player_position, asset.year, value desc
                """
        )
        players = player_cursor.fetchall()
        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        owner_cursor.execute(
            f"""SELECT
                    t3.user_id
                    , m.display_name
                    , total_value
                    , total_rank
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by max(qb_value) desc) qb_rank
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by max(rb_value) desc) rb_rank
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by max(wr_value) desc) wr_rank
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by max(te_value) desc) te_rank
                    , max(picks_value) as picks_value
                    , DENSE_RANK() OVER (order by max(picks_value) desc) picks_rank


                    from (select
                        user_id
                        , sum(value) as position_value
                        , total_value
                        , DENSE_RANK() OVER (PARTITION BY player_position  order by sum(value) desc) as position_rank
                        , DENSE_RANK() OVER (order by total_value desc) as total_rank
                        , player_position
                        , case when player_position = 'QB' THEN sum(value) else 0 end as qb_value
                        , case when player_position = 'RB' THEN sum(value) else 0 end as rb_value
                        , case when player_position = 'WR' THEN sum(value) else 0 end as wr_value
                        , case when player_position = 'TE' THEN sum(value) else 0 end as te_value
                        , case when player_position = 'PICKS' THEN sum(value) else 0 end as picks_value
                        from (SELECT
                        asset.user_id
                        , asset.league_id
                        , asset.session_id
                        , asset.season
                        , asset.year
                        , asset.full_name
                        , asset.player_name
                        , asset.player_position
                        , asset.team
                        , value  
                        , sum(value) OVER (PARTITION BY asset.user_id) as total_value    
                        from      
                        (
                        SELECT
                        lp.user_id 
                        , lp.league_id
                        , lp.session_id
                        , null as season
                        , null as year
                        , p.full_name full_name
                        , p.full_name player_name
                        , p.player_position
                        , p.team
                        , p.player_id sleeper_id
                        , coalesce(ktc.{league_type},-1) as value  

                        from dynastr.league_players lp
                        inner join dynastr.players p on lp.player_id = p.player_id
                        LEFT JOIN dynastr.ktc_player_ranks ktc on concat(p.first_name, p.last_name) = concat(ktc.player_first_name, ktc.player_last_name)
                        where 1=1
                        and session_id = '{session_id}'
                        and league_id = '{league_id}'
                        and p.player_position != 'FB'
                    UNION ALL 
                    SELECT 
                    t3.user_id
                    , t3.league_id
                    , t3.session_id
                    , t3.season
                    , t3.year
                    , t3.full_name
                    , t3.player_name
                    , t3.position
                    , t3.team
                    , t3.sleeper_id
                    , coalesce(ktc.{league_type},-1) as value  
                    FROM
                       (SELECT  
                            al.user_id
                            , al.league_id
                            , null as session_id
                            , al.season
                            , al.year 
                            , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                            ELSE al.year|| ' Mid ' || al.round_name END AS full_name
                            , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                            ELSE al.year|| ' Mid ' || al.round_name END AS player_name 
                            , 'PICKS' as position
                            , null as team
                            , null as sleeper_id
                            FROM (                           
                                SELECT dp.roster_id, dp.year, dp.round_name, dp.league_id, dpos.user_id, dpos.season
                                FROM dynastr.draft_picks dp
                                inner join dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id  

                                where 1=1
                                and dp.league_id = '{league_id}'
                                and dpos.league_id = '{league_id}'
                                and dp.session_id = '{session_id}'
                                ) al 
                            inner join dynastr.draft_positions dname on  dname.roster_id = al.roster_id
                            where 1=1 
                            and dname.league_id = '{league_id}'
                            ) t3
                    LEFT JOIN dynastr.ktc_player_ranks ktc on t3.player_name = ktc.player_full_name
                    ) asset  
                ORDER BY asset.user_id, asset.player_position, asset.year, value desc
                            ) t2
                                                group by
                                                user_id
                                                , player_position,total_value ) t3  
                                                 inner JOIN dynastr.managers m on cast(t3.user_id as varchar) = cast(m.user_id as varchar)
                                            group by
                                                t3.user_id, total_value, total_rank, m.display_name
                                            order by
                                               total_value desc"""
        )
        owners = owner_cursor.fetchall()
        qbs = [player for player in players if player["player_position"] == "QB"]
        rbs = [player for player in players if player["player_position"] == "RB"]
        wrs = [player for player in players if player["player_position"] == "WR"]
        tes = [player for player in players if player["player_position"] == "TE"]
        picks = [player for player in players if player["player_position"] == "PICKS"]

        aps = {"qb": qbs, "rb": rbs, "wr": wrs, "te": tes, "picks": picks}

        owner_cursor.close()
        player_cursor.close()

        return render_template(
            "leagues/get_league.html",
            owners=owners,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            league_type=league_type,
            aps=aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            date_=date_,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/trade_tracker", methods=["GET", "POST"])
def trade_tracker():
    db = pg_db()
    date_ = datetime.now().strftime("%m-%d-%Y")

    if request.method == "POST":
        if list(request.form)[0] == "power_rankings":
            league_data = eval(request.form["power_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.get_league",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "contender_rankings":
            league_data = eval(request.form["contender_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.contender_rankings",
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

        trades_cursor.execute(
            f"""SELECT * 
                    from 
                    (select
                    league_id
                    , transaction_id
                    , status_updated
                    , user_id
                    , transaction_type
                    , asset
                    , value
                    , display_name
                    , player_id as sleeper_id
                    , sum(value) OVER (partition by transaction_id, user_id) as owner_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , p.full_name player_name
                                    , coalesce(ktc.{league_type}, 0) as value
                                    , m.display_name
                                    , p.player_id
                                    from dynastr.player_trades pt
                                    inner join dynastr.players p on pt.player_id = p.player_id
                                    left join dynastr.ktc_player_ranks ktc on concat(p.first_name, p.last_name) = concat(ktc.player_first_name, ktc.player_last_name)
                                    inner join dynastr.draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join dynastr.managers m on cast(dp.user_id as varchar) = cast(m.user_id as varchar)
                                    where 1=1
                                    and pt.league_id = '{league_id}' 
                                    and transaction_type = 'add'
                                    --and pt.transaction_id = '832101872931274752'
                                    
                                    UNION ALL
                                    
                                    select a1.league_id
                                    ,a1.transaction_id
                                    ,a1.status_updated
                                    , a1.user_id
                                    , a1.transaction_type
                                    , case when a1.season != '{current_year}' THEN replace(a1.asset, 'Mid', '') else a1.asset end as asset
                                    , case when a1.season != '{current_year}' THEN replace(a1.asset, 'Mid', '') else a1.asset end as player_name
                                    , ktc.{league_type} as value
                                    , m.display_name
                                    , null as player_id
                                            from 
                                                ( select 
                                                dpt.league_id
                                                , transaction_id
                                                , status_updated
                                                , dp.user_id
                                                , dpt.transaction_type
                                                , case when dpt.season = dp.season 
                                                    THEN dpt.season ||' ' || ddp.position_name ||' ' ||dpt.round_suffix 
                                                    ELSE dpt.season ||' Mid ' ||dpt.round_suffix
                                                    end as asset
                                                , case when dpt.season = dp.season 
                                                    THEN dpt.season ||' ' || ddp.position_name ||' ' ||dpt.round_suffix 
                                                    ELSE dpt.season ||' Mid ' ||dpt.round_suffix
                                                    end as player_name
                                                , dp.position_name
                                                , dpt.season
                                                from dynastr.draft_pick_trades dpt
                                                inner join dynastr.draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join dynastr.draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                where 1=1  
                                                and dpt.league_id = '{league_id}' 
                                                and transaction_type = 'add'
                                                --and dpt.transaction_id IN ('832101872931274752')
                                                
                                                )  a1
                                    inner join dynastr.ktc_player_ranks ktc on a1.player_name = ktc.player_full_name
                                    inner join dynastr.managers m on cast(a1.user_id as varchar) = cast(m.user_id as varchar)
                                    
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , value  desc) t2
                                    where t2.num_managers > 1
                                    order by t2.status_updated desc"""
        )
        analytics_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        analytics_cursor.execute(
            f"""SELECT display_name
                    , count(distinct transaction_id) trades_cnt
                    , sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) as total_add
                    , sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END) as total_drop
                    , sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END) total_diff
                    , (sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END))/count(distinct transaction_id) as avg_per_trade
                    
                    from 
                    (select
                    league_id
                    , transaction_id
                    , status_updated
                    , user_id
                    , transaction_type
                    , asset
                    , value
                    , display_name
                    , player_id
                    , sum(value) OVER (partition by transaction_id, user_id) owner_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , p.full_name
                                    , coalesce(ktc.{league_type}, 0) as value
                                    , m.display_name
                                    , p.player_id
                                    from dynastr.player_trades pt
                                    inner join dynastr.players p on pt.player_id = p.player_id
                                    left join dynastr.ktc_player_ranks ktc on concat(p.first_name, p.last_name) = concat(ktc.player_first_name, ktc.player_last_name)
                                    inner join dynastr.draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join dynastr.managers m on cast(dp.user_id as varchar) = cast(m.user_id as varchar)
                                    where 1=1
                                    and pt.league_id = '{league_id}'
                                    --and transaction_type = 'add'
                                    --and pt.transaction_id = '832101872931274752'
                                    
                                    UNION ALL
                                    
                                    select a1.league_id
                                    ,a1.transaction_id
                                    ,a1.status_updated
                                    , a1.user_id
                                    , a1.transaction_type
                                    , a1.asset
                                    , a1.player_name
                                    , ktc.{league_type} as value
                                    , m.display_name
                                    , null as player_id
                                            from 
                                                ( select 
                                                dpt.league_id
                                                , transaction_id
                                                , status_updated
                                                , dp.user_id
                                                , dpt.transaction_type
                                                , case when dpt.season = dp.season 
                                                    THEN dpt.season ||' ' || ddp.position_name ||' ' ||dpt.round_suffix 
                                                    ELSE dpt.season ||' Mid ' ||dpt.round_suffix
                                                    end as asset
                                                , case when dpt.season = dp.season 
                                                    THEN dpt.season ||' ' || ddp.position_name ||' ' ||dpt.round_suffix 
                                                    ELSE dpt.season ||' Mid ' ||dpt.round_suffix
                                                    end as player_name
                                                , dp.position_name
                                                , dpt.season
                                                from dynastr.draft_pick_trades dpt
                                                inner join dynastr.draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join dynastr.draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                where 1=1
                                            -- and dpt.transaction_id = '832101872931274752'
                                                and dpt.league_id = '{league_id}' 
                                                --and transaction_type = 'add'
                                                
                                                )  a1
                                    inner join dynastr.ktc_player_ranks ktc on a1.player_name = ktc.player_full_name
                                    inner join dynastr.managers m on cast(a1.user_id as varchar) = cast(m.user_id as varchar)
                                    where 1=1 
                                    
                                    order by status_updated desc
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , value  desc) t2
                                    where t2.num_managers > 1
                    group by display_name
                    order by trades_cnt desc
                    """
        )

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

        return render_template(
            "leagues/trade_tracker.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            date_=date_,
            league_name=get_league_name(league_id),
        )


@bp.route("/contender_rankings", methods=["GET", "POST"])
def contender_rankings():
    db = pg_db()
    if request.method == "POST":
        if list(request.form)[0] == "power_rankings":
            league_data = eval(request.form["power_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            # print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id, user_id)

            return redirect(
                url_for(
                    "leagues.get_league",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "trade_tracker":

            league_data = eval(request.form["trade_tracker"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]

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

            return redirect(
                url_for(
                    "leagues.trade_tracker",
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
        contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        contenders_cursor.execute(
            f"""SELECT
                    asset.user_id 
                    , asset.league_id
                    , asset.session_id
                    , asset.year
                    , asset.full_name
                    , asset.player_position
                    , asset.team
                    , asset.sleeper_id
                    , coalesce(ep.total_projection,-1) as value
                    , ep.insert_date   
                    from      
                    (
                    SELECT
                        lp.user_id 
                        , lp.league_id
                        , lp.session_id
                        , null as season
                        , null as year
                        , p.full_name as full_name
                        , concat(p.first_name, p.last_name) player_name
                        , p.player_position
                        , p.team
                        , p.player_id as sleeper_id
                        from dynastr.league_players lp
                        inner join dynastr.players p on lp.player_id = p.player_id
                        where 1=1
                        and session_id = '{session_id}'
                        and league_id = '{league_id}'
                        and p.player_position != 'FB'                            
                    ) asset  
                LEFT JOIN dynastr.espn_player_projections ep on asset.player_name = concat(ep.player_first_name, ep.player_last_name)
                ORDER BY asset.user_id, asset.player_position, value desc
        """
        )
        contenders = contenders_cursor.fetchall()

        qbs = [player for player in contenders if player["player_position"] == "QB"]
        rbs = [player for player in contenders if player["player_position"] == "RB"]
        wrs = [player for player in contenders if player["player_position"] == "WR"]
        tes = [player for player in contenders if player["player_position"] == "TE"]

        c_aps = {"qb": qbs, "rb": rbs, "wr": wrs, "te": tes}
        c_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c_owners_cursor.execute(
            f"""SELECT 
                    t3.user_id
                    , m.display_name
                    , total_value
                    , total_rank
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by max(qb_value) desc) qb_rank
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by max(rb_value) desc) rb_rank
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by max(wr_value) desc) wr_rank
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by max(te_value) desc) te_rank

                    from (select 
                        user_id
                        , sum(value) as position_value
                        , total_value
                        , DENSE_RANK() OVER (PARTITION BY player_position  order by sum(value) desc) position_rank
                        , DENSE_RANK() OVER (order by total_value desc) total_rank
                        , player_position
                        , case when player_position = 'QB' THEN sum(value) else 0 end as qb_value
                        , case when player_position = 'RB' THEN sum(value) else 0 end as rb_value
                        , case when player_position = 'WR' THEN sum(value) else 0 end as wr_value
                        , case when player_position = 'TE' THEN sum(value) else 0 end as te_value
                        from (SELECT
                        asset.user_id 
                        , asset.league_id
                        , asset.session_id
                        , asset.full_name
                        , asset.player_position
                        , asset.team
                        , coalesce(total_projection,0) as value  
                        , sum(coalesce(total_projection,0)) OVER (PARTITION BY asset.user_id) as total_value    
                        from      
                        (
                        SELECT
                            lp.user_id 
                            ,lp.league_id
                            ,lp.session_id
                            , p.full_name full_name
                            , concat(p.first_name, p.last_name) player_name
                            , p.player_position
                            , p.team
                            from dynastr.league_players lp
                            inner join dynastr.players p on lp.player_id = p.player_id
                            where 1=1
                            and session_id = '{session_id}'
                            and league_id = '{league_id}'
                            and p.player_position != 'FB'  
                    ) asset  
                LEFT JOIN dynastr.espn_player_projections ep on asset.player_name = concat(ep.player_first_name, ep.player_last_name)
                ORDER BY asset.user_id, asset.player_position, value desc
                            ) t2
                                                group by 
                                                user_id, t2.total_value
                                                , player_position ) t3
                                                INNER JOIN dynastr.managers m on cast(t3.user_id as varchar) = cast(m.user_id as varchar)
                                                group by 
                                                t3.user_id, m.display_name, total_value, total_rank
                                                order by
                                                total_value desc
        """
        )
        c_owners = c_owners_cursor.fetchall()
        espn_date = datetime.strptime(
            contenders[0]["insert_date"], "%Y-%m-%dT%H:%M:%S.%f"
        )
        refresh_date = datetime.strftime(espn_date, "%m/%d/%Y")

        return render_template(
            "leagues/contender_rankings.html",
            owners=c_owners,
            league_name=get_league_name(league_id),
            user_name=get_user_name(user_id)[1],
            aps=c_aps,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            refresh_date=refresh_date,
        )
    else:
        return redirect(url_for("leagues.index"))

