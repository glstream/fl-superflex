import os
from flask import Flask
import requests
from datetime import datetime
from flask import send_from_directory
from calls import make_api_call


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev", DATABASE=os.path.join(app.instance_path, "dynastr.sqlite")
    )
    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.template_filter("get_user_name")
    def get_user_name(user_id: str) -> str:
        user_url = f"https://api.sleeper.app/v1/user/{user_id}"
        print(user_url)
        user_req = requests.get(user_url)
        user_meta = user_req.json()
        return user_meta["display_name"]

    @app.template_filter("get_owners")
    def get_owners(owner_values: list) -> list:
        return list(set([owner[0] for owner in owner_values]))

    @app.template_filter("suffix")
    def suffix(rank: int) -> str:
        ith = {1: "st", 2: "nd", 3: "rd"}.get(
            rank % 10 * (rank % 100 not in [11, 12, 13]), "th"
        )
        return f"{str(rank)}{ith}" if rank else ""

    @app.template_filter("sleeper_img")
    def sleeper_img(sleeper_id):
        if sleeper_id:
            return f"https://sleepercdn.com/content/nfl/players/thumb/{sleeper_id}.jpg"
        else:
            return "https://sleepercdn.com/images/v2/icons/player_default.webp"

    @app.template_filter("owner_img")
    def owner_img(avatar_id):
        if avatar_id:
            return f"https://sleepercdn.com/uploads/{avatar_id}.jpg"
        else:
            return "https://sleepercdn.com/images/v2/icons/player_default.webp"

    @app.template_filter("timestamp_convert")
    def timestamp_convert(timestamp: int) -> str:
        trade_datetime = datetime.utcfromtimestamp(int(str(timestamp)[:10]))
        return trade_datetime.strftime("%m-%d-%Y")

    @app.template_filter("league_cat")
    def league_cat(cat: int) -> str:
        category = {0: "Redraft", 1: "Keeper", 2: "Dynasty"}
        try:
            return category[cat]
        except:
            return "Redraft"

    @app.template_filter("age_adjust")
    def age_adjust(age_tile: int) -> int:
        return age_tile if age_tile < 11 else 10

    @app.template_filter("init_cap_format")
    def init_cap_format(phrase: str) -> str:
        return " ".join([i.lower().capitalize() for i in phrase.split("_")])

    @app.template_filter("get_user_name")
    def get_user_name(user_id: str) -> str:
        print(user_id)
        if user_id:
            try:
                username_url = f"https://api.sleeper.app/v1/user/{user_id}"
                user_name = requests.get(username_url).json()["display_name"]
            except:
                print("hit")
                return ""
        else:
            return ""
        print(user_name)
        return user_name

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.template_filter("select_league_ranks")
    def get_owners(rank: str) -> str:
        if rank is None:
            output = "-"
        else:
            ith = {1: "st", 2: "nd", 3: "rd"}.get(
                int(rank) % 10 * (int(rank) % 100 not in [11, 12, 13]), "th"
            )
            output = f"{rank}{ith}"
        return output

    @app.template_filter("zero_val")
    def zero_val(asset_val: str) -> str:
        return asset_val if int(asset_val.replace(",", "")) > 0 else "-"

    @app.route("/ads.txt")
    def ads_txt():
        return send_from_directory(os.path.join(app.root_path, "static"), "ads.txt")

    from . import db, leagues

    db.init_app(app)
    app.register_blueprint(leagues.bp)
    app.add_url_rule("/", endpoint="leagues.index")

    return app
