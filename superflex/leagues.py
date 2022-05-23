import functools, asyncio, os, json, requests, uuid
import socket

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

from superflex.db import get_db

bp = Blueprint("leagues", __name__, url_prefix="/")
bp.secret_key = "hello"


def n_user_id(user_name: str) -> str:
    user_url = f"https://api.sleeper.app/v1/user/{user_name}"
    un_res = requests.get(user_url)
    user_id = un_res.json()["user_id"]
    return user_id


def user_leagues(user_name: str, year="2022") -> list:
    owner_id = n_user_id(user_name)
    leagues_url = f"https://api.sleeper.app/v1/user/{owner_id}/leagues/nfl/{year}"
    leagues_res = requests.get(leagues_url)
    leagues = [
        (league["name"], league["league_id"], league["avatar"], league["total_rosters"])
        for league in leagues_res.json()
    ]
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


def insert_players(owned_players, session_id, league_id, user_id):
    own_players = []
    db = get_db()
    enrty_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    # print(f"OWNED_PLAYERS:{owned_players[-10:-1]}")
    for team in owned_players:
        if team[0] is not None:
            for player_id in team[0]:
                own_players.append(
                    [
                        session_id,
                        league_id,
                        user_id,
                        player_id,
                        team[-1],
                        team[1],
                        enrty_time,
                    ]
                )

    db.executemany(
        "INSERT INTO owned_players (session_id, owner_league_id, owner_user_id, player_id, league_id, user_id, insert_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (own_players),
    )
    db.commit()

    return


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
    draft_meta = draft.json()[-1]
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
    print(manager_data)

    return manager_data


def insert_managers(db, managers: list) -> None:
    db.executemany(
        """INSERT OR REPLACE INTO managers (source, user_id, league_id, avatar, display_name)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE
            SET source=excluded.source, league_id=excluded.league_id, avatar=excluded.avatar, display_name=excluded.display_name
            """,
        (managers),
    )
    db.commit()
    return


def round_suffix(rank: int) -> str:
    ith = {1: "st", 2: "nd", 3: "rd"}.get(
        rank % 10 * (rank % 100 not in [11, 12, 13]), "th"
    )
    return f"{str(rank)}{ith}"


def clean_league_rosters(db, session_id: str, user_id: str, league_id: str) -> None:
    delete_query = f"""DELETE FROM league_players where session_id = '{session_id}' and league_id = '{league_id}' """
    db.execute(delete_query)
    db.commit()
    print("Players Deleted")
    return


def clean_player_trades(db, league_id: str) -> None:
    delete_query = f"""DELETE FROM player_trades where league_id = '{league_id}'"""
    db.execute(delete_query)
    db.commit()
    print("Draft Picks Deleted")
    return


def clean_draft_trades(db, league_id: str) -> None:
    delete_query = f"""DELETE FROM draft_pick_trades where league_id = '{league_id}'"""
    db.execute(delete_query)
    db.commit()
    print("Draft Picks Trades Deleted")
    return


def clean_league_picks(db, session_id: str, league_id: str) -> None:
    delete_query = f"""DELETE FROM draft_picks where session_id = '{session_id}' and league_id = '{league_id}'"""
    db.execute(delete_query)
    db.commit()
    print("Draft Picks Deleted")
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
                            draft_picks_[4],  # owner_id
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

    db.executemany(
        """INSERT INTO draft_pick_trades (transaction_id, status_updated, roster_id, transaction_type, season, round, round_suffix, org_owner_id, league_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
        (draft_drops_db),
    )
    db.commit()
    db.executemany(
        """INSERT INTO draft_pick_trades (transaction_id, status_updated, roster_id, transaction_type, season, round, round_suffix, org_owner_id, league_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
        (draft_adds_db),
    )
    db.commit()
    db.executemany(
        """INSERT INTO player_trades (transaction_id, status_updated, roster_id, transaction_type, player_id, league_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
        (player_drops_db),
    )
    db.commit()
    db.executemany(
        """INSERT INTO player_trades (transaction_id, status_updated, roster_id, transaction_type, player_id, league_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
        (player_adds_db),
    )
    db.commit()

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
    db.executemany(
        """INSERT OR REPLACE INTO league_players (session_id, owner_user_id, player_id, league_id, user_id, insert_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (player_id, user_id) DO UPDATE
                SET session_id =excluded.session_id, owner_user_id =excluded.owner_user_id, player_id =excluded.player_id, league_id =excluded.league_id, user_id =excluded.user_id, insert_date=excluded.insert_date""",
        (league_players),
    )
    db.commit()


def total_owned_picks(
    db, league_id: str, session_id, base_picks: dict = {}, traded_picks_all: dict = {}
) -> dict:
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
            db.executemany(
                """INSERT INTO draft_picks (year, round, round_name, roster_id,owner_id, league_id,draft_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?,?,?)
            ON CONFLICT (year, round, roster_id, owner_id, league_id, session_id) DO UPDATE  
            SET year=excluded.year, round=excluded.round, round_name=excluded.round_name, roster_id=excluded.roster_id,owner_id=excluded.owner_id, league_id=excluded.league_id,draft_id=excluded.draft_id, session_id=excluded.session_id
            """,
                (draft_picks),
            )
            db.commit()


def draft_positions(db, league_id: str, draft_order: list = []) -> list:
    draft_id = get_draft_id(league_id)
    draft = get_draft(draft_id["draft_id"])

    season = draft["season"]
    rounds = draft["settings"]["rounds"]
    roster_slot = {int(k): v for k, v in draft["slot_to_roster_id"].items()}
    rs_dict = dict(sorted(roster_slot.items(), key=lambda item: int(item[0])))

    draft_order_dict = dict(
        sorted(draft["draft_order"].items(), key=lambda item: item[1])
    )
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

    db.executemany(
        """INSERT OR REPLACE INTO draft_positions (season, rounds,  position, position_name, roster_id, user_id, league_id, draft_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (season, rounds, position, user_id, league_id) DO UPDATE
    SET season=excluded.season, rounds=excluded.rounds, position=excluded.position, position_name=excluded.position_name, roster_id=excluded.roster_id, user_id=excluded.user_id, league_id=excluded.league_id, draft_id=excluded.draft_id
    """,
        (draft_order),
    )
    db.commit()


def insert_users(user_id: str, league_id: str):
    # INSERT USERS IN FOR LOOP FOR SELECTED_LEAGUE
    user_records = []
    db = get_db()
    # print(f"LEAGUE_ID: {league_id} {type(league_id)}")
    user_meta = get_users_data(str(league_id))
    league_name = get_league_name(league_id)
    enrty_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    for user in user_meta:
        # user_records.append([user[1],
        #         user[0],
        #         league_id,
        #         league_name,
        #         enrty_time])
        db.execute(
            """INSERT OR REPLACE INTO leagues (user_id, user_name, league_id, league_name, insert_date)
        VALUES (?,?,?,?,?)
        ON CONFLICT (user_id, league_id) DO UPDATE 
        SET user_id = ?, user_name=?, league_id=?, league_name=?, insert_date=?""",
            (
                [
                    user[1],
                    user[0],
                    league_id,
                    league_name,
                    enrty_time,
                    user[1],
                    user[0],
                    league_id,
                    league_name,
                    enrty_time,
                ]
            ),
        )
        db.commit()


def data_sql_generator(
    session_id: str, user_name: str, user_id: str, league_id: str
) -> str:
    db = get_db()
    owners_query = f"select user_name from leagues where user_id != '{user_id}' and league_id = '{league_id}' group by user_name"
    owners = db.execute(owners_query).fetchall()
    owners_list = [elt[0] for elt in owners]
    owners_list.insert(0, user_name)
    max_select = "".join([f",MAX(`{i}_PCT`) as `{i.lower()}`" for i in owners_list])
    cast_select = "".join(
        [
            f",CAST((CAST(CASE WHEN lower(l.user_name) = '{i.lower()}' THEN (count(op.player_id)) ELSE 0 END as REAL)/CAST(league_cnt as REAL) *100) as INTEGER) as `{i.lower()}_PCT`"
            for i in owners_list
        ]
    )
    query = f"""SELECT * FROM (
        (SELECT 
        full_name
        {max_select} 
        FROM 
            (select 
                    p.player_id
                    ,p.full_name
                    , count(p.player_id) as player_cnt
                    , l.user_name
                    ,lc.league_cnt
                    {cast_select}
                    from owned_players op
                    INNER JOIN players p ON op.player_id = p.player_id 
                    INNER JOIN leagues l on op.user_id = l.user_id and op.owner_league_id = l.league_id
                    INNER JOIN (select count(distinct op.league_id) as league_cnt, user_id from owned_players op group by user_id) lc on op.user_id = lc.user_id
                    where session_id= '{session_id}'
                    and owner_league_id = '{league_id}'
                     GROUP BY
            p.full_name
            ,l.user_name
            ) lo  
            INNER JOIN (select player_id FROM owned_players WHERE user_id = '{user_id}' AND league_id = '{league_id}' and session_id = '{session_id}') mo ON lo.player_id = mo.player_id

        GROUP BY full_name) 
    )
    ORDER BY `{user_name.lower()}` desc
                    """
    cursor = db.execute(query)
    data = cursor.fetchall()
    print(f"Records Returned: {len(data)}")
    if len(data) > 0:
        col_names = [description[0] for description in cursor.description]
    return (data, col_names)


async def get_api(session, call, call_type):
    if call_type == "get_leagues":
        url = "https://api.sleeper.app/v1/user/{}/leagues/nfl/2022".format(call)

        async with session.get(url, ssl=False) as response:
            if response.status == 200:
                print(url, response.status)
                payload = await response.json()
                for result in payload:
                    league_meta_tuple = result["league_id"]
                    # print(league_meta_tuple)
                    league_ids.append(
                        league_meta_tuple
                    ) if league_meta_tuple not in league_ids else None


async def get_players_api(session, call):

    url = "https://api.sleeper.app/v1/league/{}/rosters".format(call)

    async with session.get(url, ssl=False) as response:
        if response.status == 200:
            print(url, response.status)
            # league_ids.remove(call)
            payload = await response.json()
            league_metas.append(payload)
            for league_rosters in league_metas:
                for rosters in league_rosters:
                    roster_tuple = (
                        rosters["players"],
                        rosters["owner_id"],
                        rosters["league_id"],
                    )
                    players.append(
                        roster_tuple
                    ) if roster_tuple not in players else None


async def concurent_players(calls, call_name: str = "get_players"):
    tasks = [
        asyncio.create_task(get_players_api(session, call, call_name)) for call in calls
    ]
    await asyncio.gather(*tasks)


# async def con_gather(session_id, user_id, league_id, call_name: str = "get_leagues"):

#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#     if call_name == "get_leagues":
#         user_ids = [i[0] for i in league_managers(league_id, user_id)]
#     calls = (
#         [i[0] for i in league_managers(league_id, user_id)]
#         if call_name == "get_leagues"
#         else call_id
#     )
#     leagues_connector = aiohttp.TCPConnector(limit=100)
#     async with aiohttp.ClientSession(
#         connector=leagues_connector, trust_env=True
#     ) as session:
#         tasks = [
#             asyncio.create_task(get_api(session, call, call_name)) for call in calls
#         ]
#         await asyncio.gather(*tasks)

#         if len(league_ids) > 0:
#             roster_connector = aiohttp.TCPConnector(
#                 limit=20, family=socket.AF_INET, verify_ssl=False
#             )
#             async with aiohttp.ClientSession(
#                 connector=roster_connector, trust_env=True
#             ) as session:
#                 tasks = [
#                     asyncio.create_task(get_players_api(session, league_id))
#                     for league_id in league_ids
#                 ]
#                 await asyncio.gather(*tasks)

#                 # await concurent_players(league_ids)

#                 print("user_ids:", user_ids)
#                 print("user_id:", user_id)
#                 print("session_id:", session_id)
#                 print("league_id:", league_id)
#                 print("user_id:", user_id)
#                 owned_players = [i for i in players if i[1] in user_ids]
#                 delete_players(session_id, league_id, user_id)
#                 insert_players(owned_players, session_id, league_id, user_id)
#                 # return render_template('leagues/all_players_sql.html', owned_players=owned_players, session_id=session_id, user_id=user_id, league_id=league_id)


league_ids = []
league_metas = []
players = []
# START ROUTES


@bp.route("/", methods=("GET", "POST"))
def index():
    print(session.get("user_id", "NA"))
    if request.method == "GET" and "user_id" in session:
        user_name = get_user_name(session["user_id"])
        return render_template("leagues/index.html", user_name=user_name)
    if request.method == "POST":
        session_id = session["session_id"] = str(uuid.uuid4())
        user_name = request.form["username"]
        user_id = session["user_id"] = get_user_id(user_name)
        leagues = user_leagues(str(user_id))
        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        db = get_db()
        for league in leagues:
            print(league)
            db.execute(
                f"""INSERT OR REPLACE INTO current_leagues (session_id, user_id, user_name, league_id, league_name,avatar,total_rosters, insert_date)
                        VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT (session_id, league_id) DO UPDATE 
                        SET user_id = ?, user_name = ?, league_id =?, league_name=?, avatar=?, total_rosters=?, insert_date=?""",
                (
                    session_id,
                    user_id,
                    user_name,
                    league[1],
                    league[0],
                    league[2],
                    league[3],
                    entry_time,
                    user_id,
                    user_name,
                    league[1],
                    league[0],
                    league[2],
                    league[3],
                    entry_time,
                ),
            )
            db.commit()

        return redirect(url_for("leagues.select_league"))
    return render_template("leagues/index.html")


@bp.route("/select_league", methods=["GET", "POST"])
def select_league():
    session_id = session["session_id"]
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        if list(request.form)[0] == "sel_league_data":
            league_data = eval(request.form["sel_league_data"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id)

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
            draft_positions(db, league_id)
            insert_trades(db, trades, league_id)

            return redirect(
                url_for(
                    "leagues.trade_tracker",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                )
            )

    cursor = db.execute(
        f"select * from current_leagues where session_id = '{session_id}' and user_id ='{user_id}'"
    )
    leagues = cursor.fetchall()
    if len(leagues) > 0:
        return render_template("leagues/select_league.html", leagues=leagues)
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league", methods=("GET", "POST"))
def get_league():
    db = get_db()

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
            draft_positions(db, league_id)
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
        print(league_type)
        cursor = db.execute(
            f"""SELECT
                    asset.user_id 
                    , asset.league_id
                    , asset.session_id
                    , asset.year
                    , CASE WHEN asset.year = asset.season THEN asset.full_name
                            ELSE replace(asset.full_name, 'Mid ','') END AS full_name
                    , asset.full_name
                    , asset.position
                    , asset.age
                    , asset.team
                    , asset.sleeper_id
                    , coalesce(ktc.`{league_type}`,0) value   
                    from      
                    (
                    SELECT
                        lp.user_id 
                        , lp.league_id
                        , lp.session_id
                        , null as season
                        , null as year
                        , p.full_name full_name
                        , p.position
                        , p.age
                        , p.team
                        , p.player_id sleeper_id
                        -- , coalesce(ktc.sf_value,0) value
                        from league_players lp
                        inner join players p on lp.player_id = p.player_id
                        where 1=1
                        and session_id = '{session_id}'
                        and league_id = '{league_id}'
                        and p.position != 'FB'
                    UNION ALL         
                    SELECT  
                        al.user_id
                        , al.league_id
                        , null as session_id
                        , al.season
                        , al.year 
                        , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                        ELSE al.year|| ' Mid ' || al.round_name END AS full_name
                        , 'PICKS' as position
                        , null as age
                        , null as team
                        , null as sleeper_id
                        FROM (                           
                            SELECT *
                            FROM draft_picks dp
                            inner join draft_positions dpos on dp.owner_id = dpos.roster_id  

                            where 1=1
                            and dp.league_id = '{league_id}'
                            and dpos.league_id = '{league_id}'
                            and dp.session_id = '{session_id}'
                            ) al 
                        inner join draft_positions dname on  dname.roster_id = al.roster_id
                        where 1=1 
                        and dname.league_id = '{league_id}'
    
                           
                            
                    ) asset  
                INNER JOIN ktc_player_ranks ktc on lower(asset.full_name) = lower(ktc.player_name)
                ORDER BY asset.user_id, asset.position, asset.year, value desc
                """
        )
        players = cursor.fetchall()

        owners_value_cursor = db.execute(
            f"""select 
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
                        , sum(value) position_value
                        , total_value
                        , DENSE_RANK() OVER (PARTITION BY position  order by sum(value) desc) position_rank
                        , DENSE_RANK() OVER (order by total_value desc) total_rank
                        , position
                        , case when position = "QB" THEN sum(value) else 0 end as qb_value
                        , case when position = "RB" THEN sum(value) else 0 end as rb_value
                        , case when position = "WR" THEN sum(value) else 0 end as wr_value
                        , case when position = "TE" THEN sum(value) else 0 end as te_value
                        , case when position = "PICKS" THEN sum(value) else 0 end as picks_value
                        from (SELECT
                        asset.user_id 
                        , asset.league_id
                        , asset.session_id
                        , asset.season
                        , asset.year 
                        , asset.full_name
                        , asset.position
                        , asset.age
                        , asset.team
                        , coalesce(ktc.`{league_type}`,0) value  
                        , sum(coalesce(ktc.`{league_type}`,0)) OVER (PARTITION BY asset.user_id) as total_value    
                        from      
                        (
                        SELECT
                            lp.user_id 
                            ,lp.league_id
                            ,lp.session_id
                            , null as season
                            , null as year
                            , p.full_name full_name
                            , p.position
                            , p.age
                            , p.team
                            -- , coalesce(ktc.sf_value,0) value
                            from league_players lp
                            inner join players p on lp.player_id = p.player_id
                            where 1=1
                            and session_id = '{session_id}'
                            and league_id = '{league_id}'
                            and p.position != 'FB'
                        UNION ALL         
                        SELECT  
                            al.user_id
                            , al.league_id
                            , null as session_id
                            , al.season 
                            , al.year
                            , case when al.year = dname.season THEN al.year|| ' ' || dname.position_name|| ' ' || al.round_name 
                                                            ELSE al.year|| ' Mid ' || al.round_name END AS full_name
                            , 'PICKS' as position
                            , null as age
                            , null as team
                            FROM (                           
                                SELECT *
                                FROM draft_picks dp
                                inner join draft_positions dpos on dp.owner_id = dpos.roster_id  

                                where 1=1
                                and dp.league_id = '{league_id}'
                                and dp.session_id = '{session_id}'
                                and dpos.league_id = '{league_id}'
                                ) al 
                            inner join draft_positions dname on  dname.roster_id = al.roster_id
                            where 1=1 
                            and dname.league_id = '{league_id}'   
                    ) asset  
                INNER JOIN ktc_player_ranks ktc on lower(asset.full_name) = lower(ktc.player_name)
                ORDER BY asset.user_id, asset.position, asset.year, value desc
                            )
                                                group by 
                                                user_id
                                                , position ) t3
                                                INNER JOIN managers m on t3.user_id = m.user_id
                                                group by 
                                                t3.user_id
                                                order by
                                                total_value desc"""
        )
        owners = owners_value_cursor.fetchall()

        qbs = [player for player in players if player[6] == "QB"]
        rbs = [player for player in players if player[6] == "RB"]
        wrs = [player for player in players if player[6] == "WR"]
        tes = [player for player in players if player[6] == "TE"]
        picks = [player for player in players if player[6] == "PICKS"]

        aps = {"QB": qbs, "RB": rbs, "WR": wrs, "TE": tes, "PICKS": picks}

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
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/my_leagues", methods=["GET", "POST"])
def my_leagues():
    print(session)
    db = get_db()
    session_id = session["session_id"]
    user_id = session["user_id"]
    cursor = db.execute(
        f"select * from current_leagues where session_id = '{session_id}'"
    )
    leagues = cursor.fetchall()
    league_cursor = db.execute(
        f"select distinct(owner_league_id) from owned_players where session_id= '{session_id}' and owner_user_id = '{user_id}'"
    )
    leagues_ran = league_cursor.fetchall()
    if request.method == "POST":

        league_data = eval(request.form["league_data"])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]

        insert_users(user_id, league_id)

        asyncio.run(con_gather(session_id, user_id, league_id))

        return redirect(
            url_for(
                "leagues.all_players_async",
                session_id=session_id,
                user_id=user_id,
                league_id=league_id,
            )
        )

    if len(leagues) > 0:
        print(session_id)
        leagues_ran = [row[0] for row in leagues_ran]
        return render_template(
            "leagues/my_leagues.html",
            leagues=leagues,
            leagues_ran=leagues_ran,
            session_id=session_id,
            user_id=user_id,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/trade_tracker", methods=["GET", "POST"])
def trade_tracker():
    db = get_db()

    if request.method == "POST":
        if list(request.form)[0] == "power_rankings":
            league_data = eval(request.form["power_rankings"])
            session_id = league_data[0]
            user_id = league_data[1]
            league_id = league_data[2]
            print("POST SELECT LEAGUE", league_id)
            # delete data players and picks
            clean_league_rosters(db, session_id, user_id, league_id)
            clean_league_picks(db, session_id, league_id)
            # insert managers names
            managers = get_managers(league_id)
            insert_managers(db, managers)
            # insert data
            insert_league_rosters(db, session_id, user_id, league_id)
            total_owned_picks(db, league_id, session_id)
            draft_positions(db, league_id)

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
        trades_cursor = db.execute(
            f"""select * 
                    from 
                    (select
                    league_id
                    , transaction_id
                    , status_updated
                    , user_id
                    , transaction_type
                    , asset
                    , sf_value
                    , display_name
                    , player_id sleeper_id
                    , sum(sf_value) OVER (partition by transaction_id, user_id) owner_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , coalesce(ktc.sf_value, 0) sf_value
                                    , m.display_name
                                    , p.player_id
                                    from player_trades pt
                                    inner join players p on pt.player_id = p.player_id
                                    left join ktc_player_ranks ktc on replace(p.full_name,'.', '') = replace(ktc.player_name,'.','')
                                    inner join draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join managers m on dp.user_id = m.user_id
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
                                    , a1.asset
                                    , ktc.sf_value 
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
                                                , dp.position_name
                                                , dpt.season
                                                from draft_pick_trades dpt
                                                inner join draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                where 1=1  
                                                and dpt.league_id = '{league_id}' 
                                                and transaction_type = 'add'
                                                --and dpt.transaction_id IN ('832101872931274752')
                                                
                                                )  a1
                                    inner join ktc_player_ranks ktc on a1.asset = ktc.player_name
                                    inner join managers m on a1.user_id = m.user_id
                                    
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , sf_value  desc) t2
                                    where t2.num_managers > 1
                                    order by t2.status_updated desc"""
        )
        analytics_cursor = db.execute(
            f""" select display_name
                    , count(distinct transaction_id) trades_cnt
                    , sum(CASE WHEN transaction_type = 'add' THEN sf_value ELSE 0 END) as total_add
                    , sum(CASE WHEN transaction_type = 'drop' THEN sf_value ELSE 0 END) as total_drop
                    , sum(CASE WHEN transaction_type = 'add' THEN sf_value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN sf_value ELSE 0 END) total_diff
                    , (sum(CASE WHEN transaction_type = 'add' THEN sf_value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN sf_value ELSE 0 END))/count(distinct transaction_id) as avg_per_trade
                    
                    from 
                    (select
                    league_id
                    , transaction_id
                    , status_updated
                    , user_id
                    , transaction_type
                    , asset
                    , sf_value
                    , display_name
                    , player_id
                    , sum(sf_value) OVER (partition by transaction_id, user_id) owner_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , coalesce(ktc.sf_value, 0) sf_value
                                    , m.display_name
                                    , p.player_id
                                    from player_trades pt
                                    inner join players p on pt.player_id = p.player_id
                                    left join ktc_player_ranks ktc on replace(p.full_name,'.', '') = replace(ktc.player_name,'.','')
                                    inner join draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join managers m on dp.user_id = m.user_id
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
                                    , ktc.sf_value 
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
                                                , dp.position_name
                                                , dpt.season
                                                from draft_pick_trades dpt
                                                inner join draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                where 1=1
                                            -- and dpt.transaction_id = '832101872931274752'
                                                and dpt.league_id = '{league_id}' 
                                                --and transaction_type = 'add'
                                                
                                                )  a1
                                    inner join ktc_player_ranks ktc on a1.asset = ktc.player_name
                                    inner join managers m on a1.user_id = m.user_id
                                    where 1=1 
                                    
                                    order by status_updated desc
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , sf_value  desc) t2
                                    where t2.num_managers > 1
                    group by display_name
                    order by trades_cnt desc
                    """
        )

        trades = trades_cursor.fetchall()
        summary_table = analytics_cursor.fetchall()
        transaction_ids = list(set([(i[1], i[2]) for i in trades]))
        transaction_ids = sorted(
            transaction_ids,
            key=lambda x: datetime.utcfromtimestamp(int(str(x[-1])[:10])),
            reverse=True,
        )
        managers_list = list(set([(i[7], i[1]) for i in trades]))
        trades_dict = {}
        for transaction_id in transaction_ids:
            trades_dict[transaction_id[0]] = {
                i[0]: [p for p in trades if p[7] == i[0]]
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
        )


@bp.route("/all_players_async", methods=["GET", "POST"])
def all_players_async():
    user_id = request.args.get("user_id")
    session_id = request.args.get("session_id")
    league_id = request.args.get("league_id")
    user_name = get_user_name(user_id)[-1]

    all_data = data_sql_generator(session_id, user_name, user_id, league_id)
    data = all_data[0]
    col_names = all_data[1]
    if len(data) > 0:
        league_name = get_league_name(league_id)
        return render_template(
            "leagues/all_players_async.html",
            data=data,
            col_names=col_names,
            user_name=user_name,
            session_id=session_id,
            owned_league=league_id,
            user_id=user_id,
            league_name=league_name,
        )
    else:
        return redirect(url_for("leagues.index"))

