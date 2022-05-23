from pathlib import Path
import os
import pandas as pd
import sqlite3


import os, requests, json
from pathlib import Path

top_dir = os.getcwd()

# CONFIGS
data_path = os.path.join(top_dir, "base_players.txt")
player_url = "https://api.sleeper.app/v1/players/nfl"

req = requests.get(player_url)

with open(data_path, "w") as player_file:
    json.dump(req.json(), player_file)


flasker_db_name = os.path.join(top_dir, "dynastr.sqlite")

con = sqlite3.connect(flasker_db_name)
cur = con.cursor()


# base_dir = os.getcwd()
# data_path = Path(f"{base_dir}/data/")
# players_path = data_path / "base_players.txt"

players_df = pd.read_json(data_path)

all_players_df = players_df.T

all_players_df = all_players_df.reset_index()

all_players_df = all_players_df.drop(columns=["index"])

# active_player_mask = (all_players_df["search_rank"] != 9_999_999)
# # & ( all_players_df["depth_chart_order"].notnull())

# active_players_df = all_players_df[active_player_mask]

trimmed_players_df = all_players_df[
    ["player_id", "full_name", "position", "age", "team", "search_rank"]
]

trimmed_players_df.to_sql("players", con, if_exists="replace", index=False)
print(f"Players Loaded or Instered: {len(trimmed_players_df)}")
con.close()
