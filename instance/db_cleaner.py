import sqlite3, os


db_name = "/home/graymatter/fl-superflex/instance/dynastr.sqlite"

con = sqlite3.connect(db_name)
cur = con.cursor()

con.execute("DELETE FROM player_trades")
con.commit()

con.execute("DELETE FROM draft_pick_trades")
con.commit()

con.execute("DELETE FROM league_players")
con.commit()


con.execute("DELETE FROM draft_positions")
con.commit()

con.execute("DELETE FROM draft_positions")
con.commit()

con.execute("DELETE FROM managers")
con.commit()
