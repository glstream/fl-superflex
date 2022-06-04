import requests, json, os


filters = {
    "players": {
        "filterStatsForExternalIds": {"value": [2021, 2022]},
        "filterSlotIds": {
            "value": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                23,
                24,
            ]
        },
        "filterStatsForSourceIds": {"value": [0, 1]},
        "sortAppliedStatTotal": {
            "sortAsc": False,
            "sortPriority": 3,
            "value": "102022",
        },
        "sortDraftRanks": {"sortPriority": 2, "sortAsc": True, "value": "PPR"},
        "sortPercOwned": {"sortPriority": 4, "sortAsc": False},
        "limit": 1075,
        "offset": 0,
        "filterRanksForScoringPeriodIds": {"value": [1]},
        "filterRanksForRankTypes": {"value": ["PPR"]},
        "filterRanksForSlotIds": {"value": [0, 2, 4, 6, 17, 16]},
        "filterStatsForTopScoringPeriodIds": {
            "value": 2,
            "additionalValue": ["002022", "102022", "002021", "022022"],
        },
    }
}

headers = {"x-fantasy-filter": json.dumps(filters)}

season = "2022"
url = f"https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3?scoringPeriodId=0&view=kona_player_info"
req = requests.get(url, headers=headers)
res = req.json()

top_dir = os.getcwd()

# CONFIGS
data_path = os.path.join(top_dir, "espn_projections.txt")

with open(data_path, "w") as file:
    file.write(json.dumps(res["players"]))

