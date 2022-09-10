import requests, uuid
import psycopg2
from psycopg2.extras import execute_batch, execute_values
from pathlib import Path
import os


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
                    roster["owner_id"] if roster["owner_id"] is not None else "EMPTY",
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
                print("DRAFT_POSITION", k, "ROSTER_ID", v)
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
        """INSERT INTO dynastr.current_leagues (session_id, user_id, user_name, league_id, league_name, avatar, total_rosters, qb_cnt, rb_cnt, wr_cnt, te_cnt, flex_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
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
        rf_cnt = excluded.rf_cnt;
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
) -> None:

    if button == "trade_tracker":
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
    else:
        clean_league_managers(db, league_id)
        clean_league_rosters(db, session_id, user_id, league_id)
        clean_league_picks(db, league_id)
        clean_draft_positions(db, league_id)

        managers = get_managers(league_id)
        insert_managers(db, managers)

        insert_league_rosters(db, session_id, user_id, league_id)
        total_owned_picks(db, league_id, session_id)
        draft_positions(db, league_id, user_id)

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

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt  from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}'"
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
        print("LEAGUE_TYPE", league_type)
        folder = Path("sql/")
        print(folder)
        fp_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        print("FILE_PATH", Path.cwd())
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
        rec_flex = [
            player for player in fp_players if player["fantasy_position"] == "REC_FLEX"
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
            "rec_flex": rec_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        fp_team_spots = {"starters": fp_starters, "bench": fp_bench}

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
            "rec_flex": rec_flex,
        }

        bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        picks_ = {"picks": picks}
        team_spots = {"starters": starters, "bench": bench, "picks": picks_}

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
            "rec_flex": rec_flex,
        }

        bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        picks_ = {"picks": picks}
        team_spots = {"starters": starters, "bench": bench, "picks": picks_}

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
        rec_flex = [
            player for player in contenders if player["fantasy_position"] == "REC_FLEX"
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
            "rec_flex": rec_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        c_aps = {"starters": fp_starters, "bench": fp_bench}

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
        rec_flex = [
            player for player in contenders if player["fantasy_position"] == "REC_FLEX"
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
            "rec_flex": rec_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        nfl_aps = {"starters": fp_starters, "bench": fp_bench}

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
                ,ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY ep.total_projection desc) rn

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
        rec_flex = [
            player for player in contenders if player["fantasy_position"] == "REC_FLEX"
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
            "rec_flex": rec_flex,
        }
        fp_bench = {"qb": bench_qbs, "rb": bench_rbs, "wr": bench_wrs, "te": bench_tes}
        fp_aps = {"starters": fp_starters, "bench": fp_bench}

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
                ,ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY ep.total_projection desc) rn

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
