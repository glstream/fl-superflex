import json, os, sqlite3
from datetime import datetime

top_dir = os.getcwd()
flasker_db_name = os.path.join(top_dir, "dynastr.sqlite")

# con = sqlite3.connect("/home/graymatter/fl-superflex/instance/dynastr.sqlite")
con = sqlite3.connect(flasker_db_name)
cur = con.cursor()

top_dir = os.getcwd()

# CONFIGS
data_path = os.path.join(top_dir, "espn_projections.txt")

with open(data_path, "r") as player_data:
    players = json.load(player_data)

enrty_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

espn_players = []
for player in players:
    espn_players.append(
        [
            player["player"]["fullName"],
            player["id"],
            player["player"]["draftRanksByRankType"]["PPR"].get("rank", -1),
            player["player"]["draftRanksByRankType"]["PPR"].get("auctionValue", -1),
            round(player["player"]["stats"][-1].get("appliedTotal", 0)),
            round(player["player"]["stats"][-1]["stats"].get("53", 0)),
            round(player["player"]["stats"][-1]["stats"].get("42", 0)),
            round(player["player"]["stats"][-1]["stats"].get("43", 0)),
            round(player["player"]["stats"][-1]["stats"].get("23", 0)),
            round(player["player"]["stats"][-1]["stats"].get("24", 0)),
            round(player["player"]["stats"][-1]["stats"].get("25", 0)),
            round(player["player"]["stats"][-1]["stats"].get("0", 0)),
            round(player["player"]["stats"][-1]["stats"].get("1", 0)),
            round(player["player"]["stats"][-1]["stats"].get("3", 0)),
            round(player["player"]["stats"][-1]["stats"].get("4", 0)),
            round(player["player"]["stats"][-1]["stats"].get("20", 0)),
            enrty_time,
        ]
    )

    con.executemany(
        """INSERT OR REPLACE INTO espn_player_projections (
        player_name,
        espn_player_id,
        ppr_rank,
        ppr_auction_value,
        total_projection,
        recs,
        rec_yards,
        rec_tds,
        carries,
        rush_yards,
        rush_tds,
        pass_attempts,
        pass_completions,
        pass_yards,
        pass_tds,
        pass_ints,
        insert_date
)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT (espn_player_id) DO UPDATE
SET ppr_rank=excluded.ppr_rank,
    ppr_auction_value=excluded.ppr_auction_value,
    total_projection=excluded.total_projection,
    recs=excluded.recs,
    rec_yards=excluded.rec_yards,
    rec_tds=excluded.rec_tds,
    carries=excluded.carries,
    rush_yards=excluded.rush_yards,
    rush_tds=excluded.rush_tds,
    pass_attempts=excluded.pass_attempts,
    pass_completions=excluded.pass_completions,
    pass_yards=excluded.pass_yards,
    pass_tds=excluded.pass_tds,
    pass_ints=excluded.pass_ints""",
        (espn_players),
    )
con.commit()

print(f"{len(espn_players)} espn players to inserted or updated.")
