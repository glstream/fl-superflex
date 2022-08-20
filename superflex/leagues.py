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
        (user_meta["display_name"], user_meta["user_id"], user_meta["avatar"])
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
                            , display_name = EXCLUDED.display_name;
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
    try:
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
    except:
        pass

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
            , roster_id = EXCLUDED.roster_id
            , draft_id = EXCLUDED.draft_id
    ;""",
        tuple(draft_order),
        page_size=1000,
    )
    new_values = [
        (i["owner_id"], str(i["roster_id"]))
        for i in requests.get(
            f"https://api.sleeper.app/v1/league/{league_id}/rosters"
        ).json()
    ]
    update_query = f"""UPDATE dynastr.draft_positions AS t 
                    SET user_id = e.user_id 
                    FROM (VALUES %s) AS e(user_id, roster_id) 
                    WHERE e.roster_id = t.roster_id and t.league_id = '{league_id}';"""

    execute_values(cursor, update_query, new_values, template=None, page_size=100)
    # update_draft_positions = """UPDATE dynastr.draft_positions SET user_id = t.new_user_id from (i['roster_id'], i['owner_id']) as t(roster_id, new_user_id) where dynastr.draft_positions.roster_id = t.roster_id"""
    db.commit()
    cursor.close()
    return


def insert_current_leagues(
    db, session_id: str, user_id: str, user_name: str, entry_time: str, leagues: list
) -> None:
    cursor = db.cursor()
    execute_batch(
        cursor,
        """INSERT INTO dynastr.current_leagues (session_id, user_id, user_name, league_id, league_name, avatar, total_rosters, qb_cnt, rb_cnt, wr_cnt, te_cnt, flex_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
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
      	insert_date = excluded.insert_date;
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
                )
                for league in iter(leagues)
            ]
        ),
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
    session["session_id"] = str(uuid.uuid4())
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
    if request.method == "POST" and is_user(request.form["username"]):
        session_id = session.get("session_id", str(uuid.uuid4()))
        user_name = request.form["username"]
        user_id = session["user_id"] = get_user_id(user_name)
        leagues = user_leagues(str(user_id))
        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

        insert_current_leagues(db, session_id, user_id, user_name, entry_time, leagues)

        return redirect(url_for("leagues.select_league"))
    return render_template("leagues/index.html")


@bp.route("/select_league", methods=["GET", "POST"])
def select_league():
    # db = get_db()
    db = pg_db()
    if request.method == "GET" and session.get("session_id", "No_user") == "No_user":
        return redirect(url_for("leagues.index"))

    session_id = session.get("session_id", str(uuid.uuid4()))
    user_id = session["user_id"]

    if request.method == "POST":
        if list(request.form)[0] == "ktc_rankings":
            league_data = eval(request.form["ktc_rankings"])
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
        if list(request.form)[0] == "fp_rankings":
            league_data = eval(request.form["fp_rankings"])
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
                    "leagues.get_league_fp",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "dp_rankings":
            league_data = eval(request.form["dp_rankings"])
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
                    "leagues.get_league_dp",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "sel_trade_tracker":
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
        if list(request.form)[0] == "contender_rankings":
            league_data = eval(request.form["contender_rankings"])
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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "ktc_rankings":
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
        if list(request.form)[0] == "dp_rankings":
            print(request.form)
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
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
        print("LEAGUE_TYPE", league_type)

        fp_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_cursor.execute(
            f"""WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, fp.fp_player_id
, pl.player_position
, coalesce(fp.{lt}_rank_ecr, 529) as player_value
, RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(fp.{lt}_rank_ecr, 529) asc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))   

, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.fp_player_id
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.fp_player_id
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.fp_player_id
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.fp_player_id
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.fp_player_id
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.fp_player_id
, fp.player_id
, fp.player_position
, RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.fp_player_id = fp.fp_player_id
where 1=1
--and lower(fp.user_id) in ('432367510474461184','342397313982976000')
and s.fp_player_id IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.fp_player_id
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.fp_player_id
, fp.player_id
, fp.player_position
, RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
where s.fp_player_id IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.fp_player_id
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position asc)
						  
select tp.user_id
,m.display_name
,p.full_name
,lower(p.first_name) as first_name
,lower(p.last_name) as last_name
,p.team
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(fp.{lt}_rank_ecr, 545) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.fp_player_id
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.fp_player_id
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner join dynastr.fp_player_ranks fp on tp.fp_player_id = fp.fp_player_id
inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value asc"""
        )
        fp_players = fp_cursor.fetchall()

        starting_qbs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_rbs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_wrs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_tes = [
            player
            for player in fp_players
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "STARTER"
        ]
        flex = [player for player in fp_players if player["fantasy_position"] == "FLEX"]
        super_flex = [
            player
            for player in fp_players
            if player["fantasy_position"] == "SUPER_FLEX"
        ]
        bench_qbs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_rbs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_wrs = [
            player
            for player in fp_players
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_tes = [
            player
            for player in fp_players
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "BENCH"
        ]

        fp_starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        fp_team_spots = {"starters": fp_starters, "bench": fp_bench}

        fp_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_owners_cursor.execute(
            f"""with base as (SELECT 
user_id
, display_name
, player_position
, avg_position_value
, position_cnt
, avg_value
, total_value
, case when player_position = 'QB' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as qb_avg_rank
, case when player_position = 'QB' then total_position_value end as qb_total_value
, case when player_position = 'RB' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as rb_avg_rank
, case when player_position = 'RB' then total_position_value end as rb_total_value
, case when player_position = 'WR' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as wr_avg_rank
, case when player_position = 'WR' then total_position_value end as wr_total_value
, case when player_position = 'TE' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as te_avg_rank
, case when player_position = 'TE' then total_position_value end as te_total_value
, case when fantasy_designation = 'BENCH' then DENSE_RANK() OVER (PARTITION BY fantasy_designation order by avg_fantasy_value asc) end as bench_avg_rank
, case when fantasy_designation = 'BENCH' then total_fasntasy_value end as bench_total_value
, case when fantasy_designation = 'STARTER' then DENSE_RANK() OVER (PARTITION BY fantasy_designation order by avg_fantasy_value asc) end as starters_avg_rank
, case when fantasy_designation = 'STARTER' then total_fasntasy_value end as starter_total_value

, DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) position_rank
from (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    , avg(all_players.player_value) OVER (PARTITION BY all_players.user_id) as avg_value 
	  			    , count(all_players.full_name) OVER (PARTITION BY all_players.user_id, all_players.player_position) as position_cnt 
					, avg(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.player_position) as avg_position_value
	  				, sum(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.player_position) as total_position_value
	  				, avg(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.fantasy_designation) as avg_fantasy_value 
	  				, sum(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.fantasy_designation) as total_fasntasy_value
                    from (with base_players as (SELECT
                        lp.user_id
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name 
                        , pl.player_id
                        , fp.fp_player_id
                        , pl.player_position
                        , coalesce(fp.sf_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(fp.sf_rank_ecr, 529) asc) as player_order
                        , qb_cnt
                        , rb_cnt
                        , wr_cnt
                        , te_cnt
                        , flex_cnt
                        , sf_cnt

                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                        where lp.session_id = '{session_id}'
                        and lp.league_id = '{league_id}'
                        and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))   

                        , starters as (select  
                        qb.user_id
                        , qb.player_id
                        , qb.fp_player_id
                        , qb.player_position
                        , qb.player_position as fantasy_position
                        , qb.player_order
                        from base_players qb
                        where 1=1
                        and qb.player_position = 'QB'
                        and qb.player_order <= qb.qb_cnt
                        UNION ALL
                        select 
                        rb.user_id
                        , rb.player_id
                        , rb.fp_player_id
                        , rb.player_position
                        , rb.player_position as fantasy_position
                        , rb.player_order
                        from base_players rb
                        where 1=1
                        and rb.player_position = 'RB'
                        and rb.player_order <= rb.rb_cnt
                        UNION ALL
                        select 
                        wr.user_id
                        , wr.player_id
                        , wr.fp_player_id
                        , wr.player_position
                        , wr.player_position as fantasy_position
                        , wr.player_order
                        from base_players wr
                        where wr.player_position = 'WR'
                        and wr.player_order <= wr.wr_cnt

                        UNION ALL
                        select 
                        te.user_id
                        , te.player_id
                        , te.fp_player_id
                        , te.player_position
                        , te.player_position as fantasy_position
                        , te.player_order
                        from 	
                        base_players te
                        where te.player_position = 'TE'
                        and te.player_order <= te.te_cnt
                        )

                        , flex as (
                        SELECT
                        ns.user_id
                        , ns.player_id
                        , ns.fp_player_id
                        , ns.player_position
                        , 'FLEX' as fantasy_position
                        , ns.player_order
                        from (
                        SELECT
                        fp.user_id
                        , fp.fp_player_id
                        , fp.player_id
                        , fp.player_position
                        , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
                        , fp.flex_cnt
                        from base_players fp
                        left join starters s on s.fp_player_id = fp.fp_player_id
                        where 1=1
                        and s.fp_player_id IS NULL
                        and fp.player_position IN ('RB','WR','TE')  
                        order by player_order) ns
                        where player_order <= ns.flex_cnt)

                        ,super_flex as (
                        SELECT
                        ns_sf.user_id
                        , ns_sf.player_id
                        , ns_sf.fp_player_id
                        , ns_sf.player_position
                        , 'SUPER_FLEX' as fantasy_position
                        , ns_sf.player_order
                        from (
                        SELECT
                        fp.user_id
                        , fp.fp_player_id
                        , fp.player_id
                        , fp.player_position
                        , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
                        , fp.sf_cnt
                        from base_players fp
                        left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
                        where s.fp_player_id IS NULL
                        and fp.player_position IN ('QB','RB','WR','TE')  
                        order by player_order) ns_sf
                        where player_order <= ns_sf.sf_cnt)

                        , all_starters as (select 
                        user_id
                        ,ap.player_id
                        ,ap.fp_player_id
                        ,ap.player_position 
                        ,ap.fantasy_position
                        ,'STARTER' as fantasy_designation
                        ,ap.player_order
                        from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                        order by user_id, player_position asc)
                                                
                        select tp.user_id
                        ,m.display_name
                        ,p.full_name
                        ,p.team
                        ,tp.player_id as sleeper_id
                        ,tp.player_position
                        ,tp.fantasy_position
                        ,tp.fantasy_designation
                        ,fp.sf_rank_ecr as player_value
                        from (select 
                                user_id
                                ,ap.player_id
                                ,ap.fp_player_id
                                ,ap.player_position 
                                ,ap.fantasy_position
                                ,'STARTER' as fantasy_designation
                                ,ap.player_order 
                                from all_starters ap
                                UNION
                                select 
                                bp.user_id
                                ,bp.player_id
                                ,bp.fp_player_id
                                ,bp.player_position 
                                ,bp.player_position as fantasy_position
                                ,'BENCH' as fantasy_designation
                                ,bp.player_order
                                from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
                        inner join dynastr.players p on tp.player_id = p.player_id
                        inner join dynastr.fp_player_ranks fp on tp.fp_player_id = fp.fp_player_id
                        inner join dynastr.managers m on tp.user_id = m.user_id 
                        order by m.display_name, player_value asc) all_players)
						t1 
						group by 
						user_id
						,display_name
						,player_position
			  			,fantasy_designation
						,avg_position_value
			            ,avg_fantasy_value
						,position_cnt
						,avg_value
						,total_value
			  			,total_position_value
			  			,total_fasntasy_value
			 )
	
SELECT 
base.user_id
,display_name 
,total_value
,round(avg_value) as total_avg
,DENSE_RANK() OVER (order by total_value asc) total_rank
,NTILE(10) OVER (order by total_value asc) total_tile
,DENSE_RANK() OVER (order by avg_value asc) avg_rank
,NTILE(10) OVER (order by avg_value asc) avg_tile
,qb_avg_rank
,NTILE(10) OVER (order by qb_avg_rank asc) qb_avg_tile
,qb_total_value
,rb.rb_avg_rank
,NTILE(10) OVER (order by rb.rb_avg_rank asc) rb_avg_tile
,rb.rb_total_value
,wr.wr_avg_rank
,NTILE(10) OVER (order by wr.wr_avg_rank asc) wr_avg_tile
,wr.wr_total_value
,te.te_avg_rank
,NTILE(10) OVER (order by te.te_avg_rank asc) te_avg_tile
,te.te_total_value
,bench.bench_avg_rank
,NTILE(10) OVER (order by bench.bench_avg_rank asc) bench_avg_tile
,bench.bench_total_value
,starter.starters_avg_rank 
,NTILE(10) OVER (order by starter.starters_avg_rank asc) starters_avg_tile
,starter.starter_total_value
from base
inner join (SELECT user_id ,rb_avg_rank, rb_total_value from base where rb_avg_rank is not null) rb on base.user_id = rb.user_id
inner join (SELECT user_id ,wr_avg_rank, wr_total_value from base where wr_avg_rank is not null) wr on base.user_id = wr.user_id
inner join (SELECT user_id ,te_avg_rank, te_total_value from base where te_avg_rank is not null) te on base.user_id = te.user_id
inner join (SELECT user_id ,bench_avg_rank, bench_total_value from base where bench_avg_rank is not null) bench on base.user_id = bench.user_id
inner join (SELECT user_id ,starters_avg_rank, starter_total_value from base where starters_avg_rank is not null) starter on base.user_id = starter.user_id

where qb_avg_rank is not null 
group by
base.user_id
,display_name 
,total_value
,avg_value
,qb_avg_rank
,qb_total_value
,rb.rb_avg_rank
,rb.rb_total_value
,wr.wr_avg_rank
,wr.wr_total_value
,te.te_avg_rank
,te.te_total_value
,bench.bench_avg_rank
,bench.bench_total_value
,starter.starters_avg_rank
,starter.starter_total_value
order by 
total_avg asc
						"""
        )
        fp_owners = fp_owners_cursor.fetchall()

        labels = [row["display_name"] for row in fp_owners]
        values = [row["total_avg"] for row in fp_owners]
        total_value = [int(row["total_avg"]) for row in fp_owners][0] * 0.95

        pct_values = [
            100 - abs((total_value / int(row["total_avg"])) - 1) * 100
            for row in fp_owners
        ]

        fp_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_ba_cursor.execute(
            f"""SELECT 
            ba_t1.player_id as sleeper_id
            , ba_t1.full_name
            , ba_t1.player_position
            , ba_t1.player_value
            from (select
            pl.player_id
            ,pl.full_name
            ,pl.player_position
            , fp.{lt}_rank_ecr as player_value
            , ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY fp.{lt}_rank_ecr asc) rn

            from dynastr.players pl 
            inner join dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name)  = concat(fp.player_first_name, fp.player_last_name)
            where 1=1 
            and pl.player_id NOT IN (SELECT
                            lp.player_id
                            from dynastr.league_players lp
                            where lp.session_id = '{session_id}'
                            and lp.league_id = '{league_id}'
                        )
            and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
            and pl.team is not null
            order by player_value desc) ba_t1
            where ba_t1.rn <= 5
            order by ba_t1.player_position, ba_t1.player_value asc"""
        )
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        fp_owners_cursor.close()
        fp_cursor.close()
        date_cursor.close()
        fp_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league_fp.html",
            owners=fp_owners,
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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_rankings":
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
        if list(request.form)[0] == "dp_rankings":
            print(request.form)
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
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
            f"""WITH base_players as (SELECT
                    lp.user_id
                    , lp.league_id
                    , lp.session_id
                    , pl.player_id
                    , ktc.ktc_player_id
                    , pl.player_position
                    , coalesce(ktc.{league_type}, -1) as player_value
                    , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ktc.{league_type}, -1) desc) as player_order
                    , qb_cnt
                    , rb_cnt
                    , wr_cnt
                    , te_cnt
                    , flex_cnt
                    , sf_cnt

                    FROM dynastr.league_players lp
                    INNER JOIN dynastr.players pl on lp.player_id = pl.player_id
                    LEFT JOIN dynastr.ktc_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
                    INNER JOIN dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                    WHERE lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
                    and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))

                    , base_picks as (SELECT t1.user_id
                                , t1.season
                                , t1.year
                                , t1.player_name
                                , ktc.ktc_player_id
                                FROM (
                                    SELECT  
                                    al.user_id
                                    , al.season
                                    , al.year 
                                    , CASE WHEN al.year = dname.season 
                                            THEN al.year|| ' ' || dname.position_name || ' ' || al.round_name 
                                            ELSE al.year|| ' Mid ' || al.round_name 
                                            END AS player_name 
                                    FROM (                           
                                        SELECT dp.roster_id
                                        , dp.year
                                        , dp.round_name
                                        , dp.league_id
                                        , dpos.user_id
                                        , dpos.season
                                        FROM dynastr.draft_picks dp
                                        INNER JOIN dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id and dp.league_id = dpos.league_id

                                        WHERE dpos.league_id = '{league_id}'
                                        and dp.session_id = '{session_id}'
                                        ) al 
                                    INNER JOIN dynastr.draft_positions dname on  dname.roster_id = al.roster_id and al.league_id = dname.league_id
                                ) t1
                                LEFT JOIN dynastr.ktc_player_ranks ktc on t1.player_name = ktc.player_full_name
                                    )						   
                    , starters as (SELECT  
                    qb.user_id
                    , qb.player_id
                    , qb.ktc_player_id
                    , qb.player_position
                    , qb.player_position as fantasy_position
                    , qb.player_order
                    from base_players qb
                    where 1=1
                    and qb.player_position = 'QB'
                    and qb.player_order <= qb.qb_cnt
                    UNION ALL
                    SELECT 
                    rb.user_id
                    , rb.player_id
                    , rb.ktc_player_id
                    , rb.player_position
                    , rb.player_position as fantasy_position
                    , rb.player_order
                    from base_players rb
                    where 1=1
                    and rb.player_position = 'RB'
                    and rb.player_order <= rb.rb_cnt
                    UNION ALL
                    select 
                    wr.user_id
                    , wr.player_id
                    , wr.ktc_player_id
                    , wr.player_position
                    , wr.player_position as fantasy_position
                    , wr.player_order
                    from base_players wr
                    where wr.player_position = 'WR'
                    and wr.player_order <= wr.wr_cnt

                    UNION ALL
                    select 
                    te.user_id
                    , te.player_id
                    , te.ktc_player_id
                    , te.player_position
                    , te.player_position as fantasy_position
                    , te.player_order
                    from 	
                    base_players te
                    where te.player_position = 'TE'
                    and te.player_order <= te.te_cnt
                    )

                    , flex as (
                    SELECT
                    ns.user_id
                    , ns.player_id
                    , ns.ktc_player_id
                    , ns.player_position
                    , 'FLEX' as fantasy_position
                    , ns.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.flex_cnt
                    from base_players fp
                    left join starters s on s.ktc_player_id = fp.ktc_player_id
                    where 1=1
                    --and lower(fp.user_id) in ('432367510474461184','342397313982976000')
                    and s.ktc_player_id IS NULL
                    and fp.player_position IN ('RB','WR','TE')  
                    order by player_order) ns
                    where player_order <= ns.flex_cnt)

                    ,super_flex as (
                    SELECT
                    ns_sf.user_id
                    , ns_sf.player_id
                    , ns_sf.ktc_player_id
                    , ns_sf.player_position
                    , 'SUPER_FLEX' as fantasy_position
                    , ns_sf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.sf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.ktc_player_id = fp.ktc_player_id
                    where s.ktc_player_id IS NULL
                    and fp.player_position IN ('QB','RB','WR','TE')  
                    order by player_order) ns_sf
                    where player_order <= ns_sf.sf_cnt)

                    , all_starters as (select 
                    user_id
                    ,ap.player_id
                    ,ap.ktc_player_id
                    ,ap.player_position 
                    ,ap.fantasy_position
                    ,'STARTER' as fantasy_designation
                    ,ap.player_order
                    from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                    order by user_id, player_position desc)
                                            
                    SELECT tp.user_id
                    ,m.display_name
                    ,coalesce(ktc.player_full_name, tp.picks_player_name, p.full_name) as full_name
                    ,ktc.slug as hyper_link
                    ,p.team
                    ,tp.player_id as sleeper_id
                    ,tp.player_position
                    ,tp.fantasy_position
                    ,tp.fantasy_designation
                    ,coalesce(ktc.{league_type}, -1) as player_value
                    from (select 
                            user_id
                            ,ap.player_id
                            ,ap.ktc_player_id
                            ,NULL as picks_player_name
                            ,ap.player_position 
                            ,ap.fantasy_position
                            ,'STARTER' as fantasy_designation
                            ,ap.player_order 
                            from all_starters ap
                            UNION
                            select 
                            bp.user_id
                            ,bp.player_id
                            ,bp.ktc_player_id
                            ,NULL as picks_player_name
                            ,bp.player_position 
                            ,bp.player_position as fantasy_position
                            ,'BENCH' as fantasy_designation
                            ,bp.player_order
                            from base_players bp where bp.player_id not in (select player_id from all_starters)
                            UNION ALL
                            select 
                            user_id
                            ,null as player_id
                            ,picks.ktc_player_id
                            ,picks.player_name as picks_player_name
                            ,'PICKS' as player_position 
                            ,'PICKS' as fantasy_position
                            ,'PICKS' as fantasy_designation
                            , null as player_order
                            from base_picks picks
                            ) tp
                    left join dynastr.players p on tp.player_id = p.player_id
                    LEFT JOIN dynastr.ktc_player_ranks ktc on tp.ktc_player_id = ktc.ktc_player_id
                    inner join dynastr.managers m on tp.user_id = m.user_id 
                    order by m.display_name, player_value desc
                """
        )
        players = player_cursor.fetchall()

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

        picks = [
            player for player in players if player["fantasy_designation"] == "PICKS"
        ]

        starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }

        bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        picks_ = {"picks": picks}
        team_spots = {"starters": starters, "bench": bench, "picks": picks_}

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        owner_cursor.execute(
            f"""SELECT
                    t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by sum(rb_value) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value) desc) rb_tile
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , max(picks_value) as picks_value
                    , DENSE_RANK() OVER (order by sum(picks_value) desc) picks_rank
                    , NTILE(10) OVER (order by sum(picks_value) desc) picks_tile
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , DENSE_RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
					, max(Bench_value) as Bench_value
                    , DENSE_RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile


                    from (select
                        user_id
                        , display_name
                        , sum(player_value) as position_value
                        , total_value
                        , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) as position_rank
                        , DENSE_RANK() OVER (order by total_value desc) as total_rank                        , fantasy_position
                        , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                        , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                        , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                        , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                        , case when player_position = 'PICKS' THEN sum(player_value) else 0 end as picks_value
                        , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                        , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
				        , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
				        , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                        from (SELECT
                        asset.user_id
                        , asset.display_name
                        , asset.full_name
                        , asset.player_position
                        , asset.fantasy_position
                        , asset.fantasy_designation
                        , asset.team
                        , asset.player_value  
                        , sum(asset.player_value) OVER (PARTITION BY asset.user_id) as total_value    
                        from      
                        (
                        WITH base_players as (SELECT
                    lp.user_id
                    , lp.league_id
                    , lp.session_id
                    , pl.full_name 
                    , pl.player_id
                    , ktc.ktc_player_id
                    , pl.player_position
                    , coalesce(ktc.{league_type}, -1) as player_value
                    , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ktc.{league_type}, -1) desc) as player_order
                    , qb_cnt
                    , rb_cnt
                    , wr_cnt
                    , te_cnt
                    , flex_cnt
                    , sf_cnt

                    from dynastr.league_players lp
                    inner join dynastr.players pl on lp.player_id = pl.player_id
                    LEFT JOIN dynastr.ktc_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
                    inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                    where lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
                    and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))

                    , base_picks as (select t1.user_id
                                , t1.season
                                , t1.year
                                , t1.player_name
                                , ktc.ktc_player_id
                                FROM (
                                    SELECT  
                                    al.user_id
                                    , al.season
                                    , al.year 
                                    , CASE WHEN al.year = dname.season 
                                            THEN al.year|| ' ' || dname.position_name || ' ' || al.round_name 
                                            ELSE al.year|| ' Mid ' || al.round_name 
                                            END AS player_name 
                                    FROM (                           
                                        SELECT dp.roster_id
                                        , dp.year
                                        , dp.round_name
                                        , dp.league_id
                                        , dpos.user_id
                                        , dpos.season
                                        FROM dynastr.draft_picks dp
                                        inner join dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id and dp.league_id = dpos.league_id

                                        where dpos.league_id = '{league_id}'
                                        and dp.session_id = '{session_id}'
                                        ) al 
                                    inner join dynastr.draft_positions dname on  dname.roster_id = al.roster_id and al.league_id = dname.league_id
                                ) t1
                                LEFT join dynastr.ktc_player_ranks ktc on t1.player_name = ktc.player_full_name
                                    )						   
                    , starters as (SELECT  
                    qb.user_id
                    , qb.player_id
                    , qb.ktc_player_id
                    , qb.player_position
                    , qb.player_position as fantasy_position
                    , qb.player_order
                    from base_players qb
                    where 1=1
                    and qb.player_position = 'QB'
                    and qb.player_order <= qb.qb_cnt
                    UNION ALL
                    select 
                    rb.user_id
                    , rb.player_id
                    , rb.ktc_player_id
                    , rb.player_position
                    , rb.player_position as fantasy_position
                    , rb.player_order
                    from base_players rb
                    where 1=1
                    and rb.player_position = 'RB'
                    and rb.player_order <= rb.rb_cnt
                    UNION ALL
                    select 
                    wr.user_id
                    , wr.player_id
                    , wr.ktc_player_id
                    , wr.player_position
                    , wr.player_position as fantasy_position
                    , wr.player_order
                    from base_players wr
                    where wr.player_position = 'WR'
                    and wr.player_order <= wr.wr_cnt

                    UNION ALL
                    select 
                    te.user_id
                    , te.player_id
                    , te.ktc_player_id
                    , te.player_position
                    , te.player_position as fantasy_position
                    , te.player_order
                    from 	
                    base_players te
                    where te.player_position = 'TE'
                    and te.player_order <= te.te_cnt
                    )

                    , flex as (
                    SELECT
                    ns.user_id
                    , ns.player_id
                    , ns.ktc_player_id
                    , ns.player_position
                    , 'FLEX' as fantasy_position
                    , ns.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.flex_cnt
                    from base_players fp
                    left join starters s on s.ktc_player_id = fp.ktc_player_id
                    where 1=1
                    and s.ktc_player_id IS NULL
                    and fp.player_position IN ('RB','WR','TE')  
                    order by player_order) ns
                    where player_order <= ns.flex_cnt)

                    ,super_flex as (
                    SELECT
                    ns_sf.user_id
                    , ns_sf.player_id
                    , ns_sf.ktc_player_id
                    , ns_sf.player_position
                    , 'SUPER_FLEX' as fantasy_position
                    , ns_sf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.sf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.ktc_player_id = fp.ktc_player_id
                    where s.ktc_player_id IS NULL
                    and fp.player_position IN ('QB','RB','WR','TE')  
                    order by player_order) ns_sf
                    where player_order <= ns_sf.sf_cnt)

                    , all_starters as (select 
                    user_id
                    ,ap.player_id
                    ,ap.ktc_player_id
                    ,ap.player_position 
                    ,ap.fantasy_position
                    ,'STARTER' as fantasy_designation
                    ,ap.player_order
                    from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                    order by user_id, player_position desc)
                                            
                    select tp.user_id
                    ,m.display_name
                    ,ktc.player_full_name as full_name
                    ,p.team
                    ,tp.player_id as player_id
                    ,tp.player_position
                    ,tp.fantasy_position
                    ,tp.fantasy_designation
                    ,coalesce(ktc.{league_type}, -1) as player_value
                    from (select 
                            user_id
                            ,ap.player_id
                            ,ap.ktc_player_id
                            ,ap.player_position 
                            ,ap.fantasy_position
                            ,'STARTER' as fantasy_designation
                            ,ap.player_order 
                            , null as league_id
                            from all_starters ap
                            UNION
                            select 
                            bp.user_id
                            ,bp.player_id
                            ,bp.ktc_player_id
                            ,bp.player_position 
                            ,bp.player_position as fantasy_position
                            ,'BENCH' as fantasy_designation
                            ,bp.player_order
                            , bp.league_id
                            from base_players bp where bp.player_id not in (select player_id from all_starters)
                            UNION ALL
                            select 
                            user_id
                            ,null as player_id
                            ,picks.ktc_player_id
                            ,'PICKS' as player_position 
                            ,'PICKS' as fantasy_position
                            ,'PICKS' as fantasy_designation
                            , null as player_order
                            , null as league_id
                            from base_picks picks
                            ) tp
                    left join dynastr.players p on tp.player_id = p.player_id
                    inner JOIN dynastr.ktc_player_ranks ktc on tp.ktc_player_id = ktc.ktc_player_id
                    inner join dynastr.managers m on tp.user_id = m.user_id 
                    order by m.display_name, player_value desc
                    ) asset  
                            ) t2
                            GROUP BY
                             t2.user_id
                            , t2.display_name
                            , t2.total_value
                            , t2.fantasy_position
                            , t2.player_position
                            , t2.fantasy_designation) t3  
                                GROUP BY
                                    t3.user_id
                                    , t3.display_name
                                    , t3.total_value
                                    , total_rank
                                ORDER BY                                                        
                                total_value desc"""
        )
        owners = owner_cursor.fetchall()
        labels = [row["display_name"] for row in owners]
        values = [row["total_value"] for row in owners]
        total_value = [row["total_value"] for row in owners][0] * 1.05
        pct_values = [
            (((row["total_value"] - total_value) / total_value) + 1) * 100
            for row in owners
        ]

        ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ba_cursor.execute(
            f"""SELECT 
            ba_t1.player_id as sleeper_id
            , ba_t1.full_name
            , ba_t1.player_position
            , ba_t1.player_value
            from (SELECT
            pl.player_id
            ,pl.full_name
            ,pl.player_position
            , ktc.{league_type} as player_value
            , ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY ktc.{league_type} desc) rn

            FROM dynastr.players pl 
            INNER JOIN dynastr.ktc_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
            where 1=1 
            and pl.player_id NOT IN (SELECT
                            lp.player_id
                            from dynastr.league_players lp
                            where lp.session_id = '{session_id}'
                            and lp.league_id = '{league_id}'
                        )
            and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
            and pl.team is not null
            order by player_value desc) ba_t1
            where ba_t1.rn <= 5
            order by ba_t1.player_position, ba_t1.player_value desc"""
        )
        ba = ba_cursor.fetchall()
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        owner_cursor.close()
        player_cursor.close()
        ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league.html",
            owners=owners,
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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_rankings":
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
        if list(request.form)[0] == "ktc_rankings":
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
        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        player_cursor.execute(
            f"""WITH base_players as (SELECT
                    lp.user_id
                    , lp.league_id
                    , lp.session_id
                    , pl.player_id
                    , dp.fp_player_id
					, dp.player_full_name
                    , pl.player_position
                    , coalesce(dp.{league_type}, -1) as player_value
                    , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(dp.{league_type}, -1) desc) as player_order
                    , qb_cnt
                    , rb_cnt
                    , wr_cnt
                    , te_cnt
                    , flex_cnt
                    , sf_cnt

                    FROM dynastr.league_players lp
                    INNER JOIN dynastr.players pl on lp.player_id = pl.player_id
                    LEFT JOIN dynastr.dp_player_ranks dp on concat(pl.first_name, pl.last_name)  = concat(dp.player_first_name, dp.player_last_name)
                    INNER JOIN dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                    WHERE lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
                    and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))

     						   
                    , starters as (SELECT  
                    qb.user_id
                    , qb.player_id
                    , qb.fp_player_id
					, qb.player_full_name
                    , qb.player_position
                    , qb.player_position as fantasy_position
                    , qb.player_order
                    from base_players qb
                    where 1=1
                    and qb.player_position = 'QB'
                    and qb.player_order <= qb.qb_cnt
                    UNION ALL
                    SELECT 
                    rb.user_id
                    , rb.player_id
                    , rb.fp_player_id
					, rb.player_full_name
                    , rb.player_position
                    , rb.player_position as fantasy_position
                    , rb.player_order
                    from base_players rb
                    where 1=1
                    and rb.player_position = 'RB'
                    and rb.player_order <= rb.rb_cnt
                    UNION ALL
                    select 
                    wr.user_id
                    , wr.player_id
                    , wr.fp_player_id
					, wr.player_full_name
                    , wr.player_position
                    , wr.player_position as fantasy_position
                    , wr.player_order
                    from base_players wr
                    where wr.player_position = 'WR'
                    and wr.player_order <= wr.wr_cnt

                    UNION ALL
                    select 
                    te.user_id
                    , te.player_id
                    , te.fp_player_id
					, te.player_full_name
                    , te.player_position
                    , te.player_position as fantasy_position
                    , te.player_order
                    from 	
                    base_players te
                    where te.player_position = 'TE'
                    and te.player_order <= te.te_cnt
                    )

                    , flex as (
                    SELECT
                    ns.user_id
                    , ns.player_id
                    , ns.fp_player_id
					, ns.player_full_name
                    , ns.player_position
                    , 'FLEX' as fantasy_position
                    , ns.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.fp_player_id
					, fp.player_full_name
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.flex_cnt
                    from base_players fp
                    left join starters s on s.fp_player_id = fp.fp_player_id
                    where 1=1
                    and s.fp_player_id IS NULL
                    and fp.player_position IN ('RB','WR','TE')  
                    order by player_order) ns
                    where player_order <= ns.flex_cnt)

                    ,super_flex as (
                    SELECT
                    ns_sf.user_id
                    , ns_sf.player_id
                    , ns_sf.fp_player_id
					, ns_sf.player_full_name
                    , ns_sf.player_position
                    , 'SUPER_FLEX' as fantasy_position
                    , ns_sf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.fp_player_id
					, fp.player_full_name
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.sf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
                    where s.fp_player_id IS NULL
                    and fp.player_position IN ('QB','RB','WR','TE')  
                    order by player_order) ns_sf
                    where player_order <= ns_sf.sf_cnt)

                    , all_starters as (select 
                    user_id
                    ,ap.player_id
                    ,ap.fp_player_id
					,ap.player_full_name
                    ,ap.player_position 
                    ,ap.fantasy_position
                    ,'STARTER' as fantasy_designation
                    ,ap.player_order
                    from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                    order by user_id, player_position desc)
                                            
                    SELECT tp.user_id
                    ,m.display_name
                    ,coalesce(p.full_name, tp.player_full_name) as full_name
                    ,lower(p.first_name) as first_name
					,lower(p.last_name) as last_name
                    ,p.team
                    ,tp.player_id as sleeper_id
                    ,tp.player_position
                    ,tp.fantasy_position
                    ,tp.fantasy_designation
                    ,coalesce(dp.{league_type}, -1) as player_value
                    from (select 
                            user_id
                            ,ap.player_id
                            ,ap.fp_player_id
                            ,ap.player_full_name
                            ,ap.player_position 
                            ,ap.fantasy_position
                            ,'STARTER' as fantasy_designation
                            ,ap.player_order 
                            from all_starters ap
                            UNION
                            select 
                            bp.user_id
                            ,bp.player_id
                            ,bp.fp_player_id
                            ,bp.player_full_name
                            ,bp.player_position 
                            ,bp.player_position as fantasy_position
                            ,'BENCH' as fantasy_designation
                            ,bp.player_order
                            from base_players bp where bp.player_id not in (select player_id from all_starters)
                            UNION ALL
                            select 
                            user_id
                            ,null as player_id
                            ,picks.fp_player_id
                            ,picks.player_full_name as player_full_name
                            ,'PICKS' as player_position 
                            ,'PICKS' as fantasy_position
                            ,'PICKS' as fantasy_designation
                            , null as player_order
                            from (SELECT t1.user_id
                                , t1.season
                                , t1.year
                                , dp.fp_player_id
								, t1.player_full_name
								, coalesce(dp.{league_type}, -1)
                                FROM (
                                    SELECT  
                                    al.user_id
                                    , al.season
                                    , al.year 
                                    , CASE WHEN al.year = dname.season 
                                            THEN al.year|| ' ' || dname.position_name || ' ' || al.round_name 
                                            ELSE al.year|| ' Mid ' || al.round_name 
                                            END AS player_full_name 
                                    FROM (                           
                                        SELECT dp.roster_id
                                        , dp.year
                                        , dp.round_name
                                        , dp.league_id
                                        , dpos.user_id
                                        , dpos.season
                                        FROM dynastr.draft_picks dp
                                        INNER JOIN dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id and dp.league_id = dpos.league_id

                                        WHERE dpos.league_id = '{league_id}'
                                        and dp.session_id = '{session_id}'
                                        ) al 
                                    INNER JOIN dynastr.draft_positions dname on  dname.roster_id = al.roster_id and al.league_id = dname.league_id
                                ) t1
                                LEFT JOIN dynastr.dp_player_ranks dp on t1.player_full_name = dp.player_full_name
								) picks
                            ) tp
                    left join dynastr.players p on tp.player_id = p.player_id
                    LEFT JOIN dynastr.dp_player_ranks dp on tp.player_full_name = dp.player_full_name
                    inner join dynastr.managers m on tp.user_id = m.user_id 
                    order by m.display_name, player_value desc							   
                """
        )
        players = player_cursor.fetchall()

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

        picks = [
            player for player in players if player["fantasy_designation"] == "PICKS"
        ]

        starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }

        bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        picks_ = {"picks": picks}
        team_spots = {"starters": starters, "bench": bench, "picks": picks_}

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        owner_cursor.execute(
            f"""SELECT
                    t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by sum(rb_value) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value) desc) rb_tile
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , max(picks_value) as picks_value
                    , DENSE_RANK() OVER (order by sum(picks_value) desc) picks_rank
                    , NTILE(10) OVER (order by sum(picks_value) desc) picks_tile
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , DENSE_RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
					, max(Bench_value) as Bench_value
                    , DENSE_RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile


                    from (select
                        user_id
                        , display_name
                        , sum(player_value) as position_value
                        , total_value
                        , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) as position_rank
                        , DENSE_RANK() OVER (order by total_value desc) as total_rank                        , fantasy_position
                        , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                        , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                        , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                        , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                        , case when player_position = 'PICKS' THEN sum(player_value) else 0 end as picks_value
                        , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                        , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
				        , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
				        , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                        from (SELECT
                        asset.user_id
                        , asset.display_name
                        , asset.full_name
                        , asset.player_position
                        , asset.fantasy_position
                        , asset.fantasy_designation
                        , asset.team
                        , asset.player_value  
                        , sum(asset.player_value) OVER (PARTITION BY asset.user_id) as total_value    
                        from      
                        (
                        WITH base_players as (SELECT
                    lp.user_id
                    , lp.league_id
                    , lp.session_id
                    , pl.player_id
                    , ktc.fp_player_id
					, ktc.player_full_name
                    , pl.player_position
                    , coalesce(ktc.{league_type}, -1) as player_value
                    , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ktc.{league_type}, -1) desc) as player_order
                    , qb_cnt
                    , rb_cnt
                    , wr_cnt
                    , te_cnt
                    , flex_cnt
                    , sf_cnt

                    FROM dynastr.league_players lp
                    INNER JOIN dynastr.players pl on lp.player_id = pl.player_id
                    LEFT JOIN dynastr.dp_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
                    INNER JOIN dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                    WHERE lp.session_id = '{session_id}'
                    and lp.league_id = '{league_id}'
                    and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))

     						   
                    , starters as (SELECT  
                    qb.user_id
                    , qb.player_id
                    , qb.fp_player_id
					, qb.player_full_name
                    , qb.player_position
                    , qb.player_position as fantasy_position
                    , qb.player_order
                    from base_players qb
                    where 1=1
                    and qb.player_position = 'QB'
                    and qb.player_order <= qb.qb_cnt
                    UNION ALL
                    SELECT 
                    rb.user_id
                    , rb.player_id
                    , rb.fp_player_id
					, rb.player_full_name
                    , rb.player_position
                    , rb.player_position as fantasy_position
                    , rb.player_order
                    from base_players rb
                    where 1=1
                    and rb.player_position = 'RB'
                    and rb.player_order <= rb.rb_cnt
                    UNION ALL
                    select 
                    wr.user_id
                    , wr.player_id
                    , wr.fp_player_id
					, wr.player_full_name
                    , wr.player_position
                    , wr.player_position as fantasy_position
                    , wr.player_order
                    from base_players wr
                    where wr.player_position = 'WR'
                    and wr.player_order <= wr.wr_cnt

                    UNION ALL
                    select 
                    te.user_id
                    , te.player_id
                    , te.fp_player_id
					, te.player_full_name
                    , te.player_position
                    , te.player_position as fantasy_position
                    , te.player_order
                    from 	
                    base_players te
                    where te.player_position = 'TE'
                    and te.player_order <= te.te_cnt
                    )

                    , flex as (
                    SELECT
                    ns.user_id
                    , ns.player_id
                    , ns.fp_player_id
					, ns.player_full_name
                    , ns.player_position
                    , 'FLEX' as fantasy_position
                    , ns.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.fp_player_id
					, fp.player_full_name
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.flex_cnt
                    from base_players fp
                    left join starters s on s.fp_player_id = fp.fp_player_id
                    where 1=1
                    and s.fp_player_id IS NULL
                    and fp.player_position IN ('RB','WR','TE')  
                    order by player_order) ns
                    where player_order <= ns.flex_cnt)

                    ,super_flex as (
                    SELECT
                    ns_sf.user_id
                    , ns_sf.player_id
                    , ns_sf.fp_player_id
					, ns_sf.player_full_name
                    , ns_sf.player_position
                    , 'SUPER_FLEX' as fantasy_position
                    , ns_sf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.fp_player_id
					, fp.player_full_name
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.sf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
                    where s.fp_player_id IS NULL
                    and fp.player_position IN ('QB','RB','WR','TE')  
                    order by player_order) ns_sf
                    where player_order <= ns_sf.sf_cnt)

                    , all_starters as (select 
                    user_id
                    ,ap.player_id
                    ,ap.fp_player_id
					,ap.player_full_name
                    ,ap.player_position 
                    ,ap.fantasy_position
                    ,'STARTER' as fantasy_designation
                    ,ap.player_order
                    from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                    order by user_id, player_position desc)
                                            
                    SELECT tp.user_id
                    ,m.display_name
                    ,tp.player_full_name as full_name
					,lower(p.first_name) as first_name
					,lower(p.last_name) as last_name
                    ,p.team
                    ,tp.player_id as sleeper_id
                    ,tp.player_position
                    ,tp.fantasy_position
                    ,tp.fantasy_designation
                    ,coalesce(ktc.{league_type}, -1) as player_value
                    from (select 
                            user_id
                            ,ap.player_id
                            ,ap.fp_player_id
                            ,ap.player_full_name
                            ,ap.player_position 
                            ,ap.fantasy_position
                            ,'STARTER' as fantasy_designation
                            ,ap.player_order 
                            from all_starters ap
                            UNION
                            select 
                            bp.user_id
                            ,bp.player_id
                            ,bp.fp_player_id
                            ,bp.player_full_name
                            ,bp.player_position 
                            ,bp.player_position as fantasy_position
                            ,'BENCH' as fantasy_designation
                            ,bp.player_order
                            from base_players bp where bp.player_id not in (select player_id from all_starters)
                            UNION ALL
                            select 
                            user_id
                            ,null as player_id
                            ,picks.fp_player_id
                            ,picks.player_full_name as player_full_name
                            ,'PICKS' as player_position 
                            ,'PICKS' as fantasy_position
                            ,'PICKS' as fantasy_designation
                            , null as player_order
                            from (SELECT t1.user_id
                                , t1.season
                                , t1.year
                                , ktc.fp_player_id
								, t1.player_full_name
								, coalesce(ktc.{league_type}, -1)
                                FROM (
                                    SELECT  
                                    al.user_id
                                    , al.season
                                    , al.year 
                                    , CASE WHEN al.year = dname.season 
                                            THEN al.year|| ' ' || dname.position_name || ' ' || al.round_name 
                                            ELSE al.year|| ' Mid ' || al.round_name 
                                            END AS player_full_name 
                                    FROM (                           
                                        SELECT dp.roster_id
                                        , dp.year
                                        , dp.round_name
                                        , dp.league_id
                                        , dpos.user_id
                                        , dpos.season
                                        FROM dynastr.draft_picks dp
                                        INNER JOIN dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id and dp.league_id = dpos.league_id

                                        WHERE dpos.league_id = '{league_id}'
                                        and dp.session_id = '{session_id}'
                                        ) al 
                                    INNER JOIN dynastr.draft_positions dname on  dname.roster_id = al.roster_id and al.league_id = dname.league_id
                                ) t1
                                LEFT JOIN dynastr.dp_player_ranks ktc on t1.player_full_name = ktc.player_full_name
								) picks
                            ) tp
                    left join dynastr.players p on tp.player_id = p.player_id
                    LEFT JOIN dynastr.dp_player_ranks ktc on tp.player_full_name = ktc.player_full_name
                    inner join dynastr.managers m on tp.user_id = m.user_id 
                    order by m.display_name, player_value desc
				
											   
											   
                    ) asset  
                            ) t2
                            GROUP BY
                             t2.user_id
                            , t2.display_name
                            , t2.total_value
                            , t2.fantasy_position
                            , t2.player_position
                            , t2.fantasy_designation) t3  
                                GROUP BY
                                    t3.user_id
                                    , t3.display_name
                                    , t3.total_value
                                    , total_rank
                                ORDER BY                                                        
                                total_value desc"""
        )
        owners = owner_cursor.fetchall()
        labels = [row["display_name"] for row in owners]
        values = [row["total_value"] for row in owners]
        total_value = [row["total_value"] for row in owners][0] * 1.05
        pct_values = [
            (((row["total_value"] - total_value) / total_value) + 1) * 100
            for row in owners
        ]

        ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ba_cursor.execute(
            f"""SELECT 
            ba_t1.player_id as sleeper_id
            , ba_t1.full_name
            , ba_t1.player_position
            , ba_t1.player_value
            from (SELECT
            pl.player_id
            ,pl.full_name
            ,pl.player_position
            , ktc.{league_type} as player_value
            , ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY ktc.{league_type} desc) rn

            FROM dynastr.players pl 
            INNER JOIN dynastr.dp_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
            where 1=1 
            and pl.player_id NOT IN (SELECT
                            lp.player_id
                            from dynastr.league_players lp
                            where lp.session_id = '{session_id}'
                            and lp.league_id = '{league_id}'
                        )
            and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
            and pl.team is not null
            order by player_value desc) ba_t1
            where ba_t1.rn <= 5
            order by ba_t1.player_position, ba_t1.player_value desc"""
        )
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        owner_cursor.close()
        player_cursor.close()
        ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/get_league_dp.html",
            owners=owners,
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
    date_ = datetime.now().strftime("%m-%d-%Y")

    if request.method == "POST":
        if list(request.form)[0] == "fp_rankings":
            league_data = eval(request.form["fp_rankings"])
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
                    "leagues.get_league_fp",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "ktc_rankings":
            league_data = eval(request.form["ktc_rankings"])
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

        if list(request.form)[0] == "dp_rankings":
            print(request.form)
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )

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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
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
            f"""select
display_name
,trades_cnt
, NTILE(10) OVER (ORDER BY trades_cnt desc) cnt_tile
, total_add
, NTILE(10) OVER (ORDER BY total_add desc) add_tile
, total_drop
, NTILE(10) OVER (ORDER BY total_drop asc) drop_tile
, total_diff
, NTILE(10) OVER (ORDER BY total_diff desc) diff_tile
, avg_per_trade
, NTILE(10) OVER (ORDER BY avg_per_trade desc) avg_tile
from
    (SELECT display_name
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
                    order by trades_cnt desc)t3
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


@bp.route("/contender_rankings", methods=["GET", "POST"])
def contender_rankings():
    db = pg_db()
    if request.method == "POST":
        if list(request.form)[0] == "fp_rankings":
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
        if list(request.form)[0] == "ktc_rankings":
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
        if list(request.form)[0] == "dp_rankings":
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
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
            f"""WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.espn_player_id
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.espn_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.espn_player_id
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.espn_player_id
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.espn_player_id
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.espn_player_id
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.espn_player_id
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.espn_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.espn_player_id = fp.espn_player_id
where 1=1
--and lower(fp.user_id) in ('432367510474461184','342397313982976000')
and s.espn_player_id IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.espn_player_id
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.espn_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.espn_player_id = fp.espn_player_id
where s.espn_player_id IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.espn_player_id
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,p.team
,tp.espn_player_id
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.espn_player_id
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.espn_player_id
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.espn_player_projections ep on tp.espn_player_id = ep.espn_player_id

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc
        """
        )
        contenders = contenders_cursor.fetchall()

        starting_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "STARTER"
        ]
        flex = [player for player in contenders if player["fantasy_position"] == "FLEX"]
        super_flex = [
            player
            for player in contenders
            if player["fantasy_position"] == "SUPER_FLEX"
        ]
        bench_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "BENCH"
        ]

        fp_starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        c_aps = {"starters": fp_starters, "bench": fp_bench}

        c_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c_owners_cursor.execute(
            f"""SELECT 
                     t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by sum(rb_value) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value) desc) rb_tile
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , DENSE_RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
					, max(Bench_value) as Bench_value
                    , DENSE_RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile

                    from (select 
                        user_id
                    ,display_name
                    , sum(player_value) as position_value
                    , total_value
                    , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) position_rank
                    , DENSE_RANK() OVER (order by total_value desc) total_rank
                    , fantasy_position
                    , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                    , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                    , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                    , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                    , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                    , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
				    , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
				    , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                     from 
                    (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    from (WITH base_players as (SELECT
                                lp.user_id
                                , lp.league_id
                                , lp.session_id
                                , pl.full_name 
                                , pl.player_id
                                , ep.espn_player_id
                                , pl.player_position
                                , coalesce(ep.total_projection, -1) as player_value
                                , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
                                , qb_cnt
                                , rb_cnt
                                , wr_cnt
                                , te_cnt
                                , flex_cnt
                                , sf_cnt

                                from dynastr.league_players lp
                                inner join dynastr.players pl on lp.player_id = pl.player_id
                                LEFT JOIN dynastr.espn_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
                                inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
                                where lp.session_id = '{session_id}'
                                and lp.league_id = '{league_id}'
                                and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
                                                        
                                , starters as (SELECT  
                                qb.user_id
                                , qb.player_id
                                , qb.espn_player_id
                                , qb.player_position
                                , qb.player_position as fantasy_position
                                , qb.player_order
                                from base_players qb
                                where 1=1
                                and qb.player_position = 'QB'
                                and qb.player_order <= qb.qb_cnt
                                UNION ALL
                                select 
                                rb.user_id
                                , rb.player_id
                                , rb.espn_player_id
                                , rb.player_position
                                , rb.player_position as fantasy_position
                                , rb.player_order
                                from base_players rb
                                where 1=1
                                and rb.player_position = 'RB'
                                and rb.player_order <= rb.rb_cnt
                                UNION ALL
                                select 
                                wr.user_id
                                , wr.player_id
                                , wr.espn_player_id
                                , wr.player_position
                                , wr.player_position as fantasy_position
                                , wr.player_order
                                from base_players wr
                                where wr.player_position = 'WR'
                                and wr.player_order <= wr.wr_cnt

                                UNION ALL
                                select 
                                te.user_id
                                , te.player_id
                                , te.espn_player_id
                                , te.player_position
                                , te.player_position as fantasy_position
                                , te.player_order
                                from 	
                                base_players te
                                where te.player_position = 'TE'
                                and te.player_order <= te.te_cnt
                                )

                                , flex as (
                                SELECT
                                ns.user_id
                                , ns.player_id
                                , ns.espn_player_id
                                , ns.player_position
                                , 'FLEX' as fantasy_position
                                , ns.player_order
                                from (
                                SELECT
                                fp.user_id
                                , fp.espn_player_id
                                , fp.player_id
                                , fp.player_position
                                , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                                , fp.flex_cnt
                                from base_players fp
                                left join starters s on s.espn_player_id = fp.espn_player_id
                                where 1=1
                                --and lower(fp.user_id) in ('432367510474461184','342397313982976000')
                                and s.espn_player_id IS NULL
                                and fp.player_position IN ('RB','WR','TE')  
                                order by player_order) ns
                                where player_order <= ns.flex_cnt)

                                ,super_flex as (
                                SELECT
                                ns_sf.user_id
                                , ns_sf.player_id
                                , ns_sf.espn_player_id
                                , ns_sf.player_position
                                , 'SUPER_FLEX' as fantasy_position
                                , ns_sf.player_order
                                from (
                                SELECT
                                fp.user_id
                                , fp.espn_player_id
                                , fp.player_id
                                , fp.player_position
                                , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                                , fp.sf_cnt
                                from base_players fp
                                left join (select * from starters UNION ALL select * from flex) s on s.espn_player_id = fp.espn_player_id
                                where s.espn_player_id IS NULL
                                and fp.player_position IN ('QB','RB','WR','TE')  
                                order by player_order) ns_sf
                                where player_order <= ns_sf.sf_cnt)

                                , all_starters as (select 
                                user_id
                                ,ap.player_id
                                ,ap.espn_player_id
                                ,ap.player_position 
                                ,ap.fantasy_position
                                ,'STARTER' as fantasy_designation
                                ,ap.player_order
                                from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
                                order by user_id, player_position desc)
                                                        
                                select tp.user_id
                                ,m.display_name
                                ,p.full_name
                                ,p.team
                                ,tp.player_id as sleeper_id
                                ,tp.player_position
                                ,tp.fantasy_position
                                ,tp.fantasy_designation
                                ,coalesce(ep.total_projection, -1) as player_value
                                from (select 
                                        user_id
                                        ,ap.player_id
                                        ,ap.espn_player_id
                                        ,ap.player_position 
                                        ,ap.fantasy_position
                                        ,'STARTER' as fantasy_designation
                                        ,ap.player_order 
                                        from all_starters ap
                                        UNION
                                        select 
                                        bp.user_id
                                        ,bp.player_id
                                        ,bp.espn_player_id
                                        ,bp.player_position 
                                        ,bp.player_position as fantasy_position
                                        ,'BENCH' as fantasy_designation
                                        ,bp.player_order
                                        from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
                                inner join dynastr.players p on tp.player_id = p.player_id
                                inner JOIN dynastr.espn_player_projections ep on tp.espn_player_id = ep.espn_player_id
                                inner join dynastr.managers m on tp.user_id = m.user_id 
                                order by m.display_name, player_value desc)all_players
									 					) t2
                                                group by 
                                                  t2.user_id
                                                , t2.display_name
                                                , t2.total_value
                                                , t2.fantasy_position
                                                , t2.player_position
                                                , t2.fantasy_designation ) t3
                                                 group by 
                                                t3.user_id
                                                , t3.display_name
                                                , total_value
                                                , total_rank
                                                order by
                                                total_value desc"""
        )
        c_owners = c_owners_cursor.fetchall()
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
        con_ba_cursor.execute(
            f"""SELECT 
                ba_t1.player_id as sleeper_id
                , ba_t1.full_name
                , ba_t1.player_position
                , ba_t1.player_value
                from (SELECT
                pl.player_id
                ,pl.full_name
                ,pl.player_position
                ,ep.total_projection as player_value
                ,RANK() OVER(PARTITION BY pl.player_position ORDER BY ep.total_projection desc) rn

                FROM dynastr.players pl 
                INNER JOIN dynastr.espn_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
                WHERE 1=1 
                and pl.player_id NOT IN (SELECT
                                lp.player_id
                                FROM dynastr.league_players lp
                                WHERE lp.session_id = '{session_id}'
                                and lp.league_id = '{league_id}'
                            )
                and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
                and pl.team is not null
                order by player_value desc) ba_t1
                where ba_t1.rn <= 5
                order by ba_t1.player_position, ba_t1.player_value desc"""
        )
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        contenders_cursor.close()
        c_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings.html",
            owners=c_owners,
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


@bp.route("/contender_rankings_nfl", methods=["GET", "POST"])
def nfl_contender_rankings():
    db = pg_db()
    if request.method == "POST":
        if list(request.form)[0] == "fp_rankings":
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
        if list(request.form)[0] == "ktc_rankings":
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
        if list(request.form)[0] == "dp_rankings":
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
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
        nfl_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        nfl_contenders_cursor.execute(
            f"""WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.nfl_player_id
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.nfl_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.nfl_player_id
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.nfl_player_id
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.nfl_player_id
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.nfl_player_id
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.nfl_player_id
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.nfl_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.nfl_player_id = fp.nfl_player_id
where 1=1
and s.nfl_player_id IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.nfl_player_id
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.nfl_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.nfl_player_id = fp.nfl_player_id
where s.nfl_player_id IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.nfl_player_id
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,p.team
,tp.nfl_player_id
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,ep.slug as link
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.nfl_player_id
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.nfl_player_id
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.nfl_player_projections ep on tp.nfl_player_id = ep.nfl_player_id

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc
        """
        )
        contenders = nfl_contenders_cursor.fetchall()

        starting_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "STARTER"
        ]
        flex = [player for player in contenders if player["fantasy_position"] == "FLEX"]
        super_flex = [
            player
            for player in contenders
            if player["fantasy_position"] == "SUPER_FLEX"
        ]
        bench_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "BENCH"
        ]

        fp_starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        nfl_aps = {"starters": fp_starters, "bench": fp_bench}

        nfl_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        nfl_owners_cursor.execute(
            f"""SELECT 
                     t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by sum(rb_value) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value) desc) rb_tile
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , DENSE_RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
					, max(Bench_value) as Bench_value
                    , DENSE_RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile

                    from (select 
                        user_id
                    ,display_name
                    , sum(player_value) as position_value
                    , total_value
                    , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) position_rank
                    , DENSE_RANK() OVER (order by total_value desc) total_rank
                    , fantasy_position
                    , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                    , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                    , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                    , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                    , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                    , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
				    , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
				    , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                     from 
                    (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    from (WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.nfl_player_id
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.nfl_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.nfl_player_id
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.nfl_player_id
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.nfl_player_id
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.nfl_player_id
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.nfl_player_id
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.nfl_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.nfl_player_id = fp.nfl_player_id
where 1=1
and s.nfl_player_id IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.nfl_player_id
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.nfl_player_id
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.nfl_player_id = fp.nfl_player_id
where s.nfl_player_id IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.nfl_player_id
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,p.team
,tp.nfl_player_id
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.nfl_player_id
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.nfl_player_id
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.nfl_player_projections ep on tp.nfl_player_id = ep.nfl_player_id

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc)all_players
									 					) t2
                                                group by 
                                                  t2.user_id
                                                , t2.display_name
                                                , t2.total_value
                                                , t2.fantasy_position
                                                , t2.player_position
                                                , t2.fantasy_designation ) t3
                                                 group by 
                                                t3.user_id
                                                , t3.display_name
                                                , total_value
                                                , total_rank
                                                order by
                                                total_value desc"""
        )
        nfl_owners = nfl_owners_cursor.fetchall()
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
        con_ba_cursor.execute(
            f"""SELECT 
                ba_t1.player_id as sleeper_id
                , ba_t1.full_name
                , ba_t1.player_position
                , ba_t1.player_value
                from (SELECT
                pl.player_id
                ,pl.full_name
                ,pl.player_position
                ,ep.total_projection as player_value
                ,RANK() OVER(PARTITION BY pl.player_position ORDER BY ep.total_projection desc) rn

                FROM dynastr.players pl 
                INNER JOIN dynastr.nfl_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
                WHERE 1=1 
                and pl.player_id NOT IN (SELECT
                                lp.player_id
                                FROM dynastr.league_players lp
                                WHERE lp.session_id = '{session_id}'
                                and lp.league_id = '{league_id}'
                            )
                and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
                and pl.team is not null
                order by player_value desc) ba_t1
                where ba_t1.rn <= 5
                order by ba_t1.player_position, ba_t1.player_value desc"""
        )
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        nfl_contenders_cursor.close()
        nfl_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings_nfl.html",
            owners=nfl_owners,
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
        if list(request.form)[0] == "fp_rankings":
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
        if list(request.form)[0] == "ktc_rankings":
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
        if list(request.form)[0] == "dp_rankings":
            league_data = eval(request.form["dp_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            return redirect(
                url_for(
                    "leagues.get_league_dp",
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
        if list(request.form)[0] == "nfl_contender_rankings":
            league_data = eval(request.form["nfl_contender_rankings"])
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
                    "leagues.nfl_contender_rankings",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )
        if list(request.form)[0] == "fp_contender_rankings":
            league_data = eval(request.form["fp_contender_rankings"])
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
                    "leagues.fp_contender_rankings",
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
        fp_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_contenders_cursor.execute(
            f"""WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.player_full_name
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.player_full_name
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.player_full_name
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.player_full_name
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.player_full_name
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.player_full_name
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.player_full_name = fp.player_full_name
where 1=1
and s.player_full_name IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.player_full_name
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.player_full_name = fp.player_full_name
where s.player_full_name IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.player_full_name
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,lower(p.first_name) as first_name
,lower(p.last_name) as last_name
,p.team
,tp.player_full_name
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.player_full_name
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.player_full_name
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.fp_player_projections ep on tp.player_full_name = ep.player_full_name

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc
        """
        )
        contenders = fp_contenders_cursor.fetchall()

        starting_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "STARTER"
        ]
        starting_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "STARTER"
        ]
        flex = [player for player in contenders if player["fantasy_position"] == "FLEX"]
        super_flex = [
            player
            for player in contenders
            if player["fantasy_position"] == "SUPER_FLEX"
        ]
        bench_qbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "QB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_rbs = [
            player
            for player in contenders
            if player["fantasy_position"] == "RB"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_wrs = [
            player
            for player in contenders
            if player["fantasy_position"] == "WR"
            if player["fantasy_designation"] == "BENCH"
        ]
        bench_tes = [
            player
            for player in contenders
            if player["fantasy_position"] == "TE"
            if player["fantasy_designation"] == "BENCH"
        ]

        fp_starters = {
            "qb": starting_qbs,
            "rb": starting_rbs,
            "wr": starting_wrs,
            "te": starting_tes,
            "flex": flex,
            "super_flex": super_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        fp_aps = {"starters": fp_starters, "bench": fp_bench}

        fp_owners_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        fp_owners_cursor.execute(
            f"""SELECT 
                     t3.user_id
                    , t3.display_name
                    , total_value
                    , total_rank
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , DENSE_RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , max(rb_value) as rb_value
                    , DENSE_RANK() OVER (order by sum(rb_value) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value) desc) rb_tile
                    , max(wr_value) as wr_value
                    , DENSE_RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , max(te_value) as te_value
                    , DENSE_RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , max(flex_value) as flex_value
                    , DENSE_RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , DENSE_RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , DENSE_RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
					, max(Bench_value) as Bench_value
                    , DENSE_RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile

                    from (select 
                        user_id
                    ,display_name
                    , sum(player_value) as position_value
                    , total_value
                    , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) position_rank
                    , DENSE_RANK() OVER (order by total_value desc) total_rank
                    , fantasy_position
                    , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                    , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                    , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                    , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                    , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                    , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
				    , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
				    , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                     from 
                    (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    from (WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.player_full_name
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.fp_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = '{session_id}'
where lp.session_id = '{session_id}'
and lp.league_id = '{league_id}'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.player_full_name
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.player_full_name
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.player_full_name
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.player_full_name
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.player_full_name
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.player_full_name = fp.player_full_name
where 1=1
and s.player_full_name IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.player_full_name
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.player_full_name = fp.player_full_name
where s.player_full_name IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.player_full_name
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,p.team
,tp.player_full_name
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.player_full_name
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.player_full_name
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.fp_player_projections ep on tp.player_full_name = ep.player_full_name

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc)all_players
									 					) t2
                                                group by 
                                                  t2.user_id
                                                , t2.display_name
                                                , t2.total_value
                                                , t2.fantasy_position
                                                , t2.player_position
                                                , t2.fantasy_designation ) t3
                                                 group by 
                                                t3.user_id
                                                , t3.display_name
                                                , total_value
                                                , total_rank
                                                order by
                                                total_value desc"""
        )
        fp_owners = fp_owners_cursor.fetchall()
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
        con_ba_cursor.execute(
            f"""SELECT 
                ba_t1.player_id as sleeper_id
                , ba_t1.full_name
                , ba_t1.player_position
                , ba_t1.player_value
                from (SELECT
                pl.player_id
                ,pl.full_name
                ,pl.player_position
                ,ep.total_projection as player_value
                ,RANK() OVER(PARTITION BY pl.player_position ORDER BY ep.total_projection desc) rn

                FROM dynastr.players pl 
                INNER JOIN dynastr.fp_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
                WHERE 1=1 
                and pl.player_id NOT IN (SELECT
                                lp.player_id
                                FROM dynastr.league_players lp
                                WHERE lp.session_id = '{session_id}'
                                and lp.league_id = '{league_id}'
                            )
                and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
                and pl.team is not null
                order by player_value desc) ba_t1
                where ba_t1.rn <= 5
                order by ba_t1.player_position, ba_t1.player_value desc"""
        )
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
            f"select avatar from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id='{str(league_id)}'"
        )
        avatar = avatar_cursor.fetchall()

        users = get_users_data(league_id)

        fp_contenders_cursor.close()
        fp_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()

        return render_template(
            "leagues/contender_rankings_fp.html",
            owners=fp_owners,
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
        )
    else:
        return redirect(url_for("leagues.index"))
