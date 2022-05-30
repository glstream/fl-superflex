import requests, re, json
from bs4 import BeautifulSoup

from pathlib import Path
import sqlite3, os
from datetime import datetime

# top_dir = os.getcwd()
# flasker_db_name = os.path.join(top_dir, "dynastr.sqlite")

con = sqlite3.connect("/home/graymatter/fl-superflex/instance/dynastr.sqlite")
cur = con.cursor()

page = "0"
league_format = {"single_qb": "1", "sf": "2"}

ktc_base = f"https://keeptradecut.com/dynasty-rankings?page={page}&filters=QB|WR|RB|TE|RDP&format={league_format['sf']}"


res = requests.get(ktc_base)

soup = BeautifulSoup(res.text, "html.parser")

scripts = soup.find_all("script")
script_var_array = scripts[7]

# returning the string of the script tag for parsing
players_script = script_var_array.contents[0]

START_REGEX = "var playersArray ="

start_substr_num = players_script.find(START_REGEX) + len(START_REGEX) + 1

# second occurance of semicolin
end_regex = ";"
second_semicolin_num = [m.start() for m in re.finditer(r";", players_script)][1]

players_array = players_script[start_substr_num:second_semicolin_num]
ktc_players_json = json.loads(players_array)

enrty_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

ktc_players = []
for ktc_player in ktc_players_json:
    ktc_players.append(
        [
            ktc_player["playerName"],
            ktc_player["playerID"],
            ktc_player["slug"],
            ktc_player["position"],
            ktc_player["positionID"],
            ktc_player["team"],
            ktc_player["rookie"],
            ktc_player["college"],
            ktc_player["age"],
            ktc_player["heightFeet"],
            ktc_player["heightInches"],
            ktc_player["weight"],
            ktc_player["seasonsExperience"],
            ktc_player["pickRound"],
            ktc_player["pickNum"],
            ktc_player["oneQBValues"]["value"],
            ktc_player["oneQBValues"]["startSitValue"],
            ktc_player["oneQBValues"]["rank"],
            ktc_player["oneQBValues"]["overallTrend"],
            ktc_player["oneQBValues"]["positionalTrend"],
            ktc_player["oneQBValues"]["positionalRank"],
            ktc_player["oneQBValues"]["rookieRank"],
            ktc_player["oneQBValues"]["rookiePositionalRank"],
            ktc_player["oneQBValues"]["kept"],
            ktc_player["oneQBValues"]["traded"],
            ktc_player["oneQBValues"]["cut"],
            ktc_player["oneQBValues"]["overallTier"],
            ktc_player["oneQBValues"]["positionalTier"],
            ktc_player["oneQBValues"]["rookieTier"],
            ktc_player["oneQBValues"]["rookiePositionalTier"],
            ktc_player["oneQBValues"]["startSitOverallRank"],
            ktc_player["oneQBValues"]["startSitPositionalRank"],
            ktc_player["oneQBValues"]["startSitOverallTier"],
            ktc_player["oneQBValues"]["startSitPositionalTier"],
            ktc_player["oneQBValues"]["startSitOneQBFlexTier"],
            ktc_player["oneQBValues"]["startSitSuperflexFlexTier"],
            ktc_player["superflexValues"]["value"],
            ktc_player["superflexValues"]["startSitValue"],
            ktc_player["superflexValues"]["rank"],
            ktc_player["superflexValues"]["overallTrend"],
            ktc_player["superflexValues"]["positionalTrend"],
            ktc_player["superflexValues"]["positionalRank"],
            ktc_player["superflexValues"]["rookieRank"],
            ktc_player["superflexValues"]["rookiePositionalRank"],
            ktc_player["superflexValues"]["kept"],
            ktc_player["superflexValues"]["traded"],
            ktc_player["superflexValues"]["cut"],
            ktc_player["superflexValues"]["overallTier"],
            ktc_player["superflexValues"]["positionalTier"],
            ktc_player["superflexValues"]["rookieTier"],
            ktc_player["superflexValues"]["rookiePositionalTier"],
            ktc_player["superflexValues"]["startSitOverallRank"],
            ktc_player["superflexValues"]["startSitPositionalRank"],
            ktc_player["superflexValues"]["startSitOverallTier"],
            ktc_player["superflexValues"]["startSitPositionalTier"],
            enrty_time,
        ]
    )

con.executemany(
    """INSERT OR REPLACE INTO ktc_player_ranks (
        player_name,
        ktc_player_id,
        slug,
        position,
        position_id,
        team,
        rookie,
        college,
        age,
        height_feet,
        height_inches,
        weight,
        season_experience,
        pick_round,
        pink_num,
        one_qb_value,
        start_sit_value,
        rank,
        overall_trend,
        positional_trend,
        positional_rank,
        rookie_rank,
        rookie_positional_rank,
        kept,
        traded,
        cut,
        overall_tier,
        positional_tier,
        rookie_tier,
        rookie_positional_tier,
        start_sit_overall_rank,
        start_sit_positional_rank,
        start_sit_overall_tier,
        start_sit_positional_tier,
        start_sit_oneQB_flex_tier,
        start_sit_superflex_flex_tier,
        sf_value,
        sf_start_sit_value,
        sf_rank,
        sf_overall_trend,
        sf_positional_trend,
        sf_positional_rank,
        sf_rookie_rank,
        sf_rookie_positional_rank,
        sf_kept,
        sf_traded,
        sf_cut,
        sf_overall_tier,
        sf_positional_tier,
        sf_rookie_tier,
        sf_rookie_positional_tier,
        sf_start_sit_overall_rank,
        sf_start_sit_positional_rank,
        sf_start_sit_overall_tier,
        sf_start_sit_positional_tier,
        insert_date
)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT (ktc_player_id) DO UPDATE
SET sf_rank=excluded.sf_rank,one_qb_value=excluded.one_qb_value,sf_value=excluded.sf_value""",
    (ktc_players),
)
con.commit()
print(f"{len(ktc_players)} ktc players to inserted or updated.")

