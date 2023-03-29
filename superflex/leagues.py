import uuid
import psycopg2
from pathlib import Path
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from datetime import datetime
from superflex.db import pg_db
from sleeper import *
from helpers import *

bp = Blueprint("leagues", __name__, url_prefix="/")
bp.secret_key = str(uuid.uuid4())


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

        refresh_epoch = round(
            (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
        )

        player_manager_upates(db, button, session_id, user_id, league_id, startup=False)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )
    source_mapping = {
        "get_league_ktc": {
            "table": "get_league_ktc",
            "max": 12000,
            "rankings": "KeepTradeCut",
        },
        "get_league_sf": {
            "table": "get_league_sf",
            "max": 12000,
            "rankings": "SuperFlex",
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
    try:
        sf_league_type = get_league_type(league_id)
    except Exception as e:
        print(f"An error occurred: {e} on get_league_type")
        return redirect(url_for("leagues.index"))

    if sql_view_table == "get_league_ktc":
        positional_type = (
            "sf_positional_rank" if sf_league_type == "sf_value" else "positional_rank"
        )
        total_rank_type = "sf_rank" if sf_league_type == "sf_value" else "rank"
        league_type = sf_league_type

    elif sql_view_table == "get_league_fc":
        positional_type = (
            "sf_position_rank"
            if sf_league_type == "sf_value"
            else "one_qb_position_rank"
        )
        total_rank_type = (
            "sf_overall_rank" if sf_league_type == "sf_value" else "one_qb_overall_rank"
        )
        league_type = sf_league_type

    elif sql_view_table == "get_league_sf":
        positional_type = (
            "superflex_sf_pos_rank"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_pos_rank"
        )
        total_rank_type = (
            "superflex_sf_rank"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_rank"
        )
        league_type = (
            "superflex_sf_value"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_value"
        )

    elif sql_view_table == "get_league_dp":
        positional_type = ""
        total_rank_type = (
            "sf_rank_ecr" if sf_league_type == "sf_value" else "one_qb_rank_ecr"
        )
        league_type = sf_league_type

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
            .replace("sf_rank", f"{total_rank_type}")
            .replace("sf_position_rank", f"{positional_type}")
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
            .replace("league_type", f"{sf_league_type}")
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
    cur_league = league_cursor.fetchone()

    avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    avatar_cursor.execute(
        f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
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
        cur_league=cur_league,
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


@bp.route("/live_draft", methods=["GET"])
def live_draft():
    db = pg_db()
    live_draft_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    live_draft_query = """with ktc_players as (select player_full_name
,  case when team = 'KCC' then 'KC' else team end as team
, case when round(CAST(age AS float)) < 1 then Null else round(CAST(age AS float)) end as age
, sf_value as value
, sf_rank as rank
, CASE WHEN substring(lower(player_full_name) from 6 for 5) = 'round' THEN 'Pick' 
	   	WHEN position = 'RDP' THEN 'Pick'
		ELSE position END as _position
, 'sf_value' as _rank_type 
,insert_date
from dynastr.ktc_player_ranks 
UNION ALL
select player_full_name
,  case when team = 'KCC' then 'KC' else team end as team
, case when round(CAST(age AS float)) < 1 then Null else round(CAST(age AS float)) end as age
, one_qb_value as value
, rank as rank
, CASE WHEN substring(lower(player_full_name) from 6 for 5) = 'round' THEN 'Pick' 
	   	WHEN position = 'RDP' THEN 'Pick'
		ELSE position END as _position
, 'one_qb_value' as _rank_type
,insert_date
from dynastr.ktc_player_ranks )
															   
select player_full_name
,CONCAT(_position, ' ', rank() OVER (partition by _rank_type, _position ORDER BY value DESC)) as pos_rank
, team
, age
, value
, rank
, row_number() OVER (order by value desc) as _rownum
, _position
, _rank_type
, TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z')-1 as _insert_date
from ktc_players
order by value desc
									 
"""
    live_draft_cursor.execute(live_draft_query)
    players = live_draft_cursor.fetchall()
    last_refresh = players[0]["_insert_date"]
    live_draft_cursor.close()

    return render_template(
        "leagues/live_draft.html", players=players, last_refresh=last_refresh
    )


@bp.route("/sf_values", methods=["GET"])
def sf_values():
    db = pg_db()
    sf_values_cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "player_values" / "sf_values.sql", "r"
    ) as sf_values_file:
        sf_values_query = sf_values_file.read()
    sf_values_cur.execute(sf_values_query)
    players = sf_values_cur.fetchall()
    last_refresh = players[0]["_insert_date"]
    sf_values_cur.close()

    return render_template(
        "leagues/player_values/sf_values.html",
        players=players,
        last_refresh=last_refresh,
    )


@bp.route("/ktc_values", methods=["GET"])
def ktc_values():
    db = pg_db()
    ktc_values_cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "player_values" / "ktc_values.sql", "r"
    ) as ktc_values_file:
        ktc_values_query = ktc_values_file.read()
    ktc_values_cur.execute(ktc_values_query)
    players = ktc_values_cur.fetchall()
    last_refresh = players[0]["_insert_date"]
    ktc_values_cur.close()

    return render_template(
        "leagues/player_values/ktc_values.html",
        players=players,
        last_refresh=last_refresh,
    )


@bp.route("/fc_values", methods=["GET"])
def fc_values():
    db = pg_db()
    fc_values_cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "player_values" / "fc_values.sql", "r"
    ) as fc_values_file:
        fc_values_query = fc_values_file.read()
    fc_values_cur.execute(fc_values_query)
    players = fc_values_cur.fetchall()
    last_refresh = players[0]["_insert_date"]
    fc_values_cur.close()

    return render_template(
        "leagues/player_values/fc_values.html",
        players=players,
        last_refresh=last_refresh,
    )


@bp.route("/dp_values", methods=["GET"])
def dp_values():
    db = pg_db()
    dp_values_cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    with open(
        Path.cwd() / "superflex" / "sql" / "player_values" / "dp_values.sql", "r"
    ) as dp_values_file:
        dp_values_query = dp_values_file.read()
    dp_values_cur.execute(dp_values_query)
    players = dp_values_cur.fetchall()
    last_refresh = players[0]["_insert_date"]
    dp_values_cur.close()

    return render_template(
        "leagues/player_values/dp_values.html",
        players=players,
        last_refresh=last_refresh,
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
    cursor.close()

    if request.method == "GET" and "user_id" in session:
        user_name = get_user_name(session["user_id"])
        return render_template("leagues/index.html", user_name=user_name)
    if request.method == "POST":
        if is_user(request.form["username"]):
            session_id = session.get("session_id", str(uuid.uuid4()))
            user_name = request.form["username"]
            year_ = request.form.get("league_year", "2023")
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

        return redirect(url_for("leagues.select_league", year=year_))

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
            session_league_id = session["session_league_id"] = league_id

            startup_cursor = db.cursor()
            startup_cursor.execute(
                f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
            )
            try:
                startup = startup_cursor.fetchone()[0]
            except:
                startup = True
            startup_cursor.close()

            refresh_cursor = db.cursor()
            refresh_cursor.execute(
                f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
            )
            refresh = refresh_cursor.fetchone()
            refresh_cursor.close()

            if refresh is not None:
                print("HAS PLAYERS")
                refresh_date = refresh[-1]
                refresh_datetime = datetime.strptime(
                    refresh_date, "%Y-%m-%dT%H:%M:%S.%f"
                )
                refresh_epoch = round(
                    (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
                )
            else:
                refresh_epoch = round(
                    (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
                )

                player_manager_upates(
                    db, button, session_id, user_id, league_id, startup
                )
            return redirect(
                url_for(
                    f"leagues.{button}",
                    session_id=session_id,
                    league_id=league_id,
                    user_id=user_id,
                    session_league_id=session_league_id,
                    rdm=refresh_epoch,
                )
            )
    except:
        return redirect(url_for("leagues.index"))

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year  from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_year = '{str(session_year)}'"
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
    try:
        league_summary = ls_cursor.fetchall()[0]
        ls_cursor.close()
    except:
        return render_template(
            "leagues/index.html",
            error_message=f"No {session_year} leagues found for {get_user_name(user_id)[1]}, try picking a another year.",
        )

    if len(leagues) > 0:
        return render_template(
            "leagues/select_league.html", leagues=leagues, league_summary=league_summary
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league", methods=("GET", "POST"))
def get_league():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True

        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))

        league_pos_col = (
            "sf_position_rank" if league_type == "sf_value" else "one_qb_position_rank"
        )
        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd() / "superflex" / "sql" / "details" / "power" / "get_league.sql",
            "r",
        ) as get_league_detail_file:
            get_league_detail_sql = (
                get_league_detail_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
                .replace("league_pos_col", f"{league_pos_col}")
            )
        player_cursor.execute(get_league_detail_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "summary" / "power" / "get_league.sql",
            "r",
        ) as get_league_summary_file:
            get_league_summary_sql = (
                get_league_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        owner_cursor.execute(get_league_summary_sql)
        owners = owner_cursor.fetchall()
        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "picks_rank": i["picks_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "picks_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )
        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            calc_value = [row["total_value"] for row in owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "picks_total": [
                    (((int(row["picks_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
            }
        except:
            pct_values = []
            pct_values_dict = {}

        ktc_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "best_available"
            / "power"
            / "ktc_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' limit 1"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        total_rosters = int(get_league_rosters_size(league_id))

        team_spots = render_players(players, "power")

        owner_cursor.close()
        player_cursor.close()
        ktc_ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/power_ranks/get_league.html",
            owners=owners,
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
            pct_values_dict=pct_values_dict,
            best_available=best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_sf", methods=("GET", "POST"))
def get_league_sf():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            sf_league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))

        league_pos_col = (
            "superflex_sf_pos_rank"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_pos_rank"
        )
        league_type = (
            "superflex_sf_value"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_value"
        )

        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "power"
            / "get_league_sf.sql",
            "r",
        ) as get_league_detail_file:
            get_league_detail_sql = (
                get_league_detail_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
                .replace("league_pos_col", f"{league_pos_col}")
            )
        player_cursor.execute(get_league_detail_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "power"
            / "get_league_sf.sql",
            "r",
        ) as get_league_summary_file:
            get_league_summary_sql = (
                get_league_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        owner_cursor.execute(get_league_summary_sql)
        owners = owner_cursor.fetchall()
        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "picks_rank": i["picks_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "picks_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )

        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            calc_value = [row["total_value"] for row in owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "picks_total": [
                    (((int(row["picks_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
            }
        except:
            pct_values = []

        ktc_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "power" / "sf_ba.sql",
            "r",
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
        date_cursor.execute("select max(insert_date) from dynastr.sf_player_ranks")
        _date = date_cursor.fetchall()
        sf_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round((current_time - sf_max_time).total_seconds() / 60.0)
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        total_rosters = int(get_league_rosters_size(league_id))

        team_spots = render_players(players, "power")

        owner_cursor.close()
        player_cursor.close()
        ktc_ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/power_ranks/get_league_sf.html",
            owners=owners,
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
            pct_values_dict=pct_values_dict,
            best_available=best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_fc", methods=("GET", "POST"))
def get_league_fc():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except:
            return redirect(url_for("leagues.index"))
        league_pos_col = (
            "sf_position_rank" if league_type == "sf_value" else "one_qb_position_rank"
        )

        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "power"
            / "get_league_fc.sql",
            "r",
        ) as get_league_detail_file:
            get_league_detail_sql = (
                get_league_detail_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
                .replace("league_pos_col", f"{league_pos_col}")
            )
        player_cursor.execute(get_league_detail_sql)
        players = player_cursor.fetchall()

        if len(players) < 1:
            return redirect(url_for("leagues.index"))

        owner_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "power"
            / "get_league_fc.sql",
            "r",
        ) as get_league_summary_file:
            get_league_summary_sql = (
                get_league_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        owner_cursor.execute(get_league_summary_sql)
        owners = owner_cursor.fetchall()
        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "picks_rank": i["picks_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "picks_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )

        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            calc_value = [row["total_value"] for row in owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "picks_total": [
                    (((int(row["picks_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
            }
        except:
            pct_values = []

        fc_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "power" / "fc_ba.sql",
            "r",
        ) as sql_file:
            fc_sql = (
                sql_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )
        fc_ba_cursor.execute(fc_sql)
        ba = fc_ba_cursor.fetchall()

        ba_qb = [player for player in ba if player["player_position"] == "QB"]
        ba_rb = [player for player in ba if player["player_position"] == "RB"]
        ba_wr = [player for player in ba if player["player_position"] == "WR"]
        ba_te = [player for player in ba if player["player_position"] == "TE"]
        best_available = {"QB": ba_qb, "RB": ba_rb, "WR": ba_wr, "TE": ba_te}

        # Find difference in laod time and max update time in the ktc player ranks
        date_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        date_cursor.execute("select max(insert_date) from dynastr.fc_player_ranks")
        _date = date_cursor.fetchall()
        fc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round((current_time - fc_max_time).total_seconds() / 60.0)
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        total_rosters = int(get_league_rosters_size(league_id))

        team_spots = render_players(players, "power")

        owner_cursor.close()
        player_cursor.close()
        fc_ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/power_ranks/get_league_fc.html",
            owners=owners,
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
            pct_values_dict=pct_values_dict,
            best_available=best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_dp", methods=("GET", "POST"))
def get_league_dp():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))

        player_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "power"
            / "get_league_dp.sql",
            "r",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "power"
            / "get_league_dp.sql",
            "r",
        ) as get_league_dp_summary_file:
            get_league_dp_summary_sql = (
                get_league_dp_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        owner_cursor.execute(get_league_dp_summary_sql)
        owners = owner_cursor.fetchall()
        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "picks_rank": i["picks_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "picks_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )
        try:
            labels = [row["display_name"] for row in owners]
            values = [row["total_value"] for row in owners]
            calc_value = [row["total_value"] for row in owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
                "picks_total": [
                    (((int(row["picks_sum"]) - total_value) / total_value) + 1) * 100
                    for row in owners
                ],
            }
        except:
            pct_values = []

        ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd() / "superflex" / "sql" / "best_available" / "power" / "dp_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        total_rosters = get_league_rosters_size(league_id)

        owner_cursor.close()
        player_cursor.close()
        ba_cursor.close()
        date_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/power_ranks/get_league_dp.html",
            owners=owners,
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
            pct_values_dict=pct_values_dict,
            best_available=best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/get_league_fp", methods=("GET", "POST"))
def get_league_fp():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":
        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]
        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))
        lt = "sf" if league_type == "sf_value" else "one_qb"

        fp_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "power"
            / "get_league_fp.sql",
            "r",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "power"
            / "get_league_fp.sql",
            "r",
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
            Path.cwd() / "superflex" / "sql" / "best_available" / "power" / "fp_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        total_rosters = get_league_rosters_size(league_id)
        page_user = page_user if len(page_user) > 0 else ([0, 0, 0, 0, 0, 0, 0, 0])

        fp_owners_cursor.close()
        fp_cursor.close()
        date_cursor.close()
        fp_ba_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/power_ranks/get_league_fp.html",
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
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
        )


@bp.route("/trade_tracker", methods=["GET", "POST"])
def trade_tracker():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))

        trades_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "trade"
            / "trade_tracker.sql",
            "r",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "trade"
            / "trade_tracker.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1
        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        return render_template(
            "leagues/trades/trade_tracker.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            user_name=get_user_name(user_id)[1],
            cur_league=cur_league,
            avatar=avatar,
            refresh_time=refresh_time,
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
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))
        trades_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "trade"
            / "trade_tracker_fc.sql",
            "r",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "trade"
            / "trade_tracker_fc.sql",
            "r",
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

        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        return render_template(
            "leagues/trades/trade_tracker_fc.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            user_name=get_user_name(user_id)[1],
            cur_league=cur_league,
            avatar=avatar,
            refresh_time=refresh_time,
            update_diff_minutes=update_diff_minutes,
            league_name=get_league_name(league_id),
        )


@bp.route("/trade_tracker_sf", methods=["GET", "POST"])
def trade_tracker_sf():
    db = pg_db()

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            sf_league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))
        league_type = (
            "superflex_sf_value"
            if sf_league_type == "sf_value"
            else "superflex_one_qb_value"
        )
        trades_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "trade"
            / "trade_tracker_sf.sql",
            "r",
        ) as trade_tracker_sf_details_file:
            trade_tracker_sf_details_sql = (
                trade_tracker_sf_details_file.read()
                .replace("'current_year'", f"'{current_year}'")
                .replace("'league_id'", f"'{league_id}'")
                .replace("league_type", f"{league_type}")
            )

        trades_cursor.execute(trade_tracker_sf_details_sql)

        analytics_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "trade"
            / "trade_tracker_sf.sql",
            "r",
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
        date_cursor.execute("select max(insert_date) from dynastr.sf_player_ranks")
        _date = date_cursor.fetchall()
        fc_max_time = datetime.strptime(_date[0]["max"], "%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.utcnow()
        update_diff_minutes = round((current_time - fc_max_time).total_seconds() / 60.0)
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        return render_template(
            "leagues/trades/trade_tracker_sf.html",
            transaction_ids=transaction_ids,
            trades_dict=trades_dict,
            summary_table=summary_table,
            league_id=league_id,
            session_id=session_id,
            user_id=user_id,
            user_name=get_user_name(user_id)[1],
            cur_league=cur_league,
            avatar=avatar,
            refresh_time=refresh_time,
            update_diff_minutes=update_diff_minutes,
            league_name=get_league_name(league_id),
        )


@bp.route("/contender_rankings", methods=["GET", "POST"])
def contender_rankings():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")

        contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "contender"
            / "contender_rankings.sql",
            "r",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "contender"
            / "contender_rankings.sql",
            "r",
        ) as contender_rankings_summary_file:
            contender_rankings_summary_sql = (
                contender_rankings_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        c_owners_cursor.execute(contender_rankings_summary_sql)
        c_owners = c_owners_cursor.fetchall()

        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in c_owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )
        try:
            labels = [row["display_name"] for row in c_owners]
            values = [row["total_value"] for row in c_owners]
            calc_value = [row["total_value"] for row in c_owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in c_owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in c_owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in c_owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in c_owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in c_owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in c_owners
                ],
            }
        except:
            pct_values = []
            pct_values_dict = {}

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "best_available"
            / "contender"
            / "con_espn_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        contenders_cursor.close()
        c_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/contender_ranks/contender_rankings.html",
            owners=c_owners,
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
            pct_values_dict=pct_values_dict,
            best_available=con_best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_fc", methods=["GET", "POST"])
def fc_contender_rankings():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)
    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()
        print("button", button)
        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)

        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        try:
            league_type = get_league_type(league_id)
        except Exception as e:
            print(f"An error occurred: {e} on get_league_type")
            return redirect(url_for("leagues.index"))
        fc_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "contender"
            / "contender_rankings_fc.sql",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "contender"
            / "contender_rankings_fc.sql",
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

        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in fc_owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )
        try:
            labels = [row["display_name"] for row in fc_owners]
            values = [row["total_value"] for row in fc_owners]
            calc_value = [row["total_value"] for row in fc_owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in fc_owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in fc_owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fc_owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fc_owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fc_owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fc_owners
                ],
            }
        except:
            pct_values = []

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "best_available"
            / "contender"
            / "con_fc_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        fc_contenders_cursor.close()
        fc_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/contender_ranks/contender_rankings_fc.html",
            owners=fc_owners,
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
            pct_values_dict=pct_values_dict,
            best_available=con_best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_nfl", methods=["GET", "POST"])
def nfl_contender_rankings():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")
        nfl_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "contender"
            / "contender_rankings_nfl.sql",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "contender"
            / "contender_rankings_nfl.sql",
            "r",
        ) as contender_rankings_nfl_summary_file:
            contender_rankings_nfl_summary_sql = (
                contender_rankings_nfl_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        nfl_owners_cursor.execute(contender_rankings_nfl_summary_sql)

        nfl_owners = nfl_owners_cursor.fetchall()

        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in nfl_owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )
        try:
            labels = [row["display_name"] for row in nfl_owners]
            values = [row["total_value"] for row in nfl_owners]
            calc_value = [row["total_value"] for row in nfl_owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in nfl_owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in nfl_owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in nfl_owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in nfl_owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in nfl_owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in nfl_owners
                ],
            }
        except:
            pct_values = []
            pct_values_dict = {}

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "best_available"
            / "contender"
            / "con_nfl_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)
        total_rosters = get_league_rosters_size(league_id)

        nfl_contenders_cursor.close()
        nfl_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/contender_ranks/contender_rankings_nfl.html",
            owners=nfl_owners,
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
            pct_values_dict=pct_values_dict,
            best_available=con_best_available,
            avatar=avatar,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))


@bp.route("/contender_rankings_fp", methods=["GET", "POST"])
def fp_contender_rankings():
    db = pg_db()
    session_league_id = session.get("session_league_id", None)

    if request.method == "POST":

        button = list(request.form)[0]
        league_data = eval(request.form[button])
        session_id = league_data[0]
        user_id = league_data[1]
        league_id = league_data[2]
        refresh_btn = league_data[-1]

        entry_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        insert_league(db, session_id, user_id, entry_time, league_id)

        startup_cursor = db.cursor()
        startup_cursor.execute(
            f"select previous_league_id from dynastr.current_leagues where session_id = '{str(session_id)}' and user_id ='{str(user_id)}' and league_id = '{str(league_id)}' and league_status != 'in_season'"
        )
        try:
            startup = startup_cursor.fetchone()[0]
        except:
            startup = True
        startup_cursor.close()

        refresh_cursor = db.cursor()
        refresh_cursor.execute(
            f"select session_id, league_id, insert_date from dynastr.league_players where session_id = '{str(session_id)}' and league_id = '{str(league_id)}' order by TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z') desc limit 1"
        )
        refresh = refresh_cursor.fetchone()
        refresh_cursor.close()

        if refresh is not None and refresh_btn is not True:
            print("HAS PLAYERS")
            refresh_date = refresh[-1]
            refresh_datetime = datetime.strptime(refresh_date, "%Y-%m-%dT%H:%M:%S.%f")
            refresh_epoch = round(
                (refresh_datetime - datetime(1970, 1, 1)).total_seconds()
            )
        else:
            refresh_epoch = round(
                (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            )

            player_manager_upates(db, button, session_id, user_id, league_id, startup)
        return redirect(
            url_for(
                f"leagues.{button}",
                session_id=session_id,
                league_id=league_id,
                user_id=user_id,
                rdm=refresh_epoch,
            )
        )

    if request.method == "GET":
        session_id = request.args.get("session_id")
        league_id = request.args.get("league_id")
        user_id = request.args.get("user_id")
        refresh_epoch_time = request.args.get("rdm")

        fp_contenders_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "details"
            / "contender"
            / "contender_rankings_fp.sql",
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
            Path.cwd()
            / "superflex"
            / "sql"
            / "summary"
            / "contender"
            / "contender_rankings_fp.sql",
            "r",
        ) as contender_rankings_fp_summary_file:
            contender_rankings_fp_summary_sql = (
                contender_rankings_fp_summary_file.read()
                .replace("'session_id'", f"'{session_id}'")
                .replace("'league_id'", f"'{league_id}'")
            )
        fp_owners_cursor.execute(contender_rankings_fp_summary_sql)

        fp_owners = fp_owners_cursor.fetchall()

        radar_chart_data = [
            {
                "display_name": i["display_name"],
                "qb_rank": i["qb_rank"],
                "rb_rank": i["rb_rank"],
                "wr_rank": i["wr_rank"],
                "te_rank": i["te_rank"],
                "starters_rank": i["starters_rank"],
                "bench_rank": i["bench_rank"],
            }
            for i in fp_owners
            if i["user_id"] == user_id
        ][0]
        radar_chart_data = (
            radar_chart_data
            if len(radar_chart_data) > 0
            else {
                "display_name": 0,
                "qb_rank": 0,
                "rb_rank": 0,
                "wr_rank": 0,
                "te_rank": 0,
                "starters_rank": 0,
                "bench_rank": 0,
            }
        )

        try:
            labels = [row["display_name"] for row in fp_owners]
            values = [row["total_value"] for row in fp_owners]
            calc_value = [row["total_value"] for row in fp_owners][0]
            total_value = calc_value * 1.05

            pct_values = [
                (((row["total_value"] - total_value) / total_value) + 1) * 100
                for row in fp_owners
            ]
            pct_values_dict = {
                "total": [
                    (((row["total_value"] - total_value) / total_value) + 1) * 100
                    for row in fp_owners
                ],
                "qb_total": [
                    (((int(row["qb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fp_owners
                ],
                "rb_total": [
                    (((int(row["rb_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fp_owners
                ],
                "wr_total": [
                    (((int(row["wr_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fp_owners
                ],
                "te_total": [
                    (((int(row["te_sum"]) - total_value) / total_value) + 1) * 100
                    for row in fp_owners
                ],
            }
        except:
            pct_values = []
            pct_values_dict = {}

        con_ba_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        with open(
            Path.cwd()
            / "superflex"
            / "sql"
            / "best_available"
            / "contender"
            / "con_fp_ba.sql",
            "r",
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
        try:
            refresh_time = seconds_text(int(refresh_epoch_time), datetime.utcnow())
        except:
            refresh_time = -1

        avatar_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        avatar_cursor.execute(
            f"select avatar from dynastr.current_leagues where league_id='{str(league_id)}' limit 1"
        )
        avatar = avatar_cursor.fetchall()

        league_cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        league_cursor.execute(
            f"select session_id, user_id, league_id, league_name, avatar, total_rosters, qb_cnt, sf_cnt, starter_cnt, total_roster_cnt, sport, insert_date, rf_cnt, league_cat, league_year, previous_league_id  from dynastr.current_leagues where session_id = '{str(session_id)}' and league_id = '{str(league_id)}'"
        )
        cur_league = league_cursor.fetchone()

        users = get_users_data(league_id)

        nfl_current_week = get_sleeper_state()["leg"]
        total_rosters = get_league_rosters_size(league_id)

        fp_contenders_cursor.close()
        fp_owners_cursor.close()
        date_cursor.close()
        con_ba_cursor.close()
        avatar_cursor.close()
        league_cursor.close()

        return render_template(
            "leagues/contender_ranks/contender_rankings_fp.html",
            owners=fp_owners,
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
            pct_values_dict=pct_values_dict,
            best_available=con_best_available,
            avatar=avatar,
            nfl_current_week=nfl_current_week,
            cur_league=cur_league,
            session_league_id=session_league_id,
            refresh_time=refresh_time,
            radar_chart_data=radar_chart_data,
        )
    else:
        return redirect(url_for("leagues.index"))
