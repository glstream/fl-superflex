-- Initialize the database.
-- Drop any existing data and create empty tables.

-- DROP TABLE IF EXISTS dynastr.players;
DROP TABLE IF EXISTS dynastr.owned_players;
DROP TABLE IF EXISTS dynastr.leagues;
DROP TABLE IF EXISTS dynastr.current_leagues;
-- DROP TABLE IF EXISTS dynastr.ktc_player_ranks;
-- DROP TABLE IF EXISTS dynastr.espn_player_projections;  
-- DROP TABLE IF EXISTS dynastr.fp_player_ranks;
DROP TABLE IF EXISTS dynastr.league_players;
DROP TABLE IF EXISTS dynastr.draft_positions;
DROP TABLE IF EXISTS dynastr.draft_picks;
DROP TABLE IF EXISTS dynastr.player_trades;
DROP TABLE IF EXISTS dynastr.draft_pick_trades;
DROP TABLE IF EXISTS dynastr.managers;

CREATE TABLE IF NOT EXISTS dynastr.players (
  player_id VARCHAR(150) PRIMARY KEY,
  first_name VARCHAR(150),
  last_name VARCHAR(150), 
  full_name VARCHAR(150),
  player_position VARCHAR(150),
  age VARCHAR(150),
  team VARCHAR(150)
);


CREATE TABLE dynastr.leagues (
  user_id VARCHAR(75),
  user_name VARCHAR(75),
  league_id VARCHAR(75),
  league_name VARCHAR(75),
  insert_date VARCHAR(75),
  PRIMARY KEY (user_id, league_id)
);

CREATE TABLE dynastr.league_players (
  session_id VARCHAR(75),
  owner_user_id VARCHAR(75),
  player_id VARCHAR(75) ,
  league_id VARCHAR(75),
  user_id VARCHAR(75) ,
  insert_date VARCHAR(75),
  PRIMARY KEY (session_id, user_id, player_id, league_id)
);


CREATE TABLE IF NOT EXISTS dynastr.current_leagues (
  session_id VARCHAR(75),
  user_id VARCHAR(75),
  user_name VARCHAR(75),
  league_id VARCHAR(75),
  league_name VARCHAR(75),
  avatar VARCHAR(75),
  total_rosters integer,
  qb_cnt integer,
  rb_cnt integer,
  wr_cnt integer,
  te_cnt integer,
  flex_cnt integer,
  sf_cnt integer,
  starter_cnt integer,
  total_roster_cnt integer,
  sport VARCHAR(75),
  insert_date VARCHAR(75),
  rf_cnt integer,
  league_cat integer,
  league_year VARCHAR(75),
  PRIMARY KEY (session_id, league_id)
);


ALTER TABLE dynastr.current_leagues ADD rf_cnt integer;
ALTER TABLE dynastr.current_leagues ADD league_cat integer;
ALTER TABLE dynastr.current_leagues ADD league_year VARCHAR(75);
ALTER TABLE dynastr.current_leagues ADD previous_league_id VARCHAR(75);


CREATE TABLE IF NOT EXISTS dynastr.ktc_player_ranks (
  player_name VARCHAR(75),
  ktc_player_id VARCHAR(75),
  slug VARCHAR(75),
  position VARCHAR(75),
  position_id VARCHAR(75),
  team VARCHAR(75),
  rookie VARCHAR(75),
  college VARCHAR(75),
  age VARCHAR(75),
  height_feet INTEGER,
  height_inches INTEGER,
  weight INTEGER,
  season_experience INTEGER,
  pick_round INTEGER,
  pink_num INTEGER,
  one_qb_value INTEGER,
  start_sit_value INTEGER,
  rank INTEGER,
  overall_trend INTEGER,
  positional_trend INTEGER,
  positional_rank INTEGER,
  rookie_rank INTEGER,
  rookie_positional_rank INTEGER,
  kept INTEGER,
  traded INTEGER,
  cut INTEGER,
  overall_tier INTEGER,
  positional_tier INTEGER,
  rookie_tier INTEGER,
  rookie_positional_tier INTEGER,
  start_sit_overall_rank INTEGER,
  start_sit_positional_rank INTEGER,
  start_sit_overall_tier INTEGER,
  start_sit_positional_tier INTEGER,
  start_sit_oneQB_flex_tier INTEGER,
  start_sit_superflex_flex_tier INTEGER,
  sf_value INTEGER,
  sf_start_sit_value INTEGER,
  sf_rank INTEGER,
  sf_overall_trend INTEGER,
  sf_positional_trend INTEGER,
  sf_positional_rank INTEGER,
  sf_rookie_rank INTEGER,
  sf_rookie_positional_rank INTEGER,
  sf_kept INTEGER,
  sf_traded INTEGER,
  sf_cut INTEGER,
  sf_overall_tier INTEGER,
  sf_positional_tier INTEGER,
  sf_rookie_tier INTEGER,
  sf_rookie_positional_tier INTEGER,
  sf_start_sit_overall_rank INTEGER,
  sf_start_sit_positional_rank INTEGER,
  sf_start_sit_overall_tier INTEGER,
  sf_start_sit_positional_tier INTEGER,
  insert_date VARCHAR(75),
  PRIMARY KEY (ktc_player_id)
);

CREATE TABLE IF NOT EXISTS dynastr.espn_player_projections (
  player_first_name VARCHAR(150),
  player_last_name VARCHAR(150),
  player_full_name VARCHAR(150),
  espn_player_id VARCHAR(150),
  ppr_rank INTEGER,
  ppr_auction_value INTEGER,
  total_projection INTEGER,
  recs INTEGER,
  rec_yards INTEGER,
  rec_tds INTEGER,
  carries INTEGER,
  rush_yards INTEGER,
  rush_tds INTEGER,
  pass_attempts INTEGER,
  pass_completions INTEGER,
  pass_yards INTEGER,
  pass_tds INTEGER,
  pass_ints INTEGER,
  insert_date VARCHAR(75),
  PRIMARY KEY (espn_player_id)
);

CREATE TABLE IF NOT EXISTS dynastr.fp_player_ranks (
  player_first_name VARCHAR(150),
  player_last_name VARCHAR(150),
  player_full_name VARCHAR(150),
  fp_player_id VARCHAR(100),
  player_team_id VARCHAR(100),
  player_position_id VARCHAR(100),
  player_positions VARCHAR(100),
  player_short_name VARCHAR(100),
  player_eligibility VARCHAR(100),
  player_yahoo_positions VARCHAR(100),
  player_page_url VARCHAR(100),
  player_square_image_url VARCHAR(100),
  player_image_url VARCHAR(100),
  player_yahoo_id VARCHAR(100),
  cbs_player_id VARCHAR(100),
  player_bye_week VARCHAR(100),
  player_age integer,
  sf_player_ecr_delta VARCHAR(100),
  sf_rank_ecr integer,
  sf_rank_min integer,
  sf_rank_max integer,
  sf_rank_ave VARCHAR(100),
  sf_rank_std VARCHAR(100),
  sf_pos_rank VARCHAR(100),
  sf_tier integer,
  one_qb_player_ecr_delta VARCHAR(100),
  one_qb_rank_ecr integer,
  one_qb_rank_min integer,
  one_qb_rank_max integer,
  one_qb_rank_ave VARCHAR(100),
  one_qb_rank_std VARCHAR(100),
  one_qb_pos_rank VARCHAR(100),
  one_qb_tier integer,
  insert_date VARCHAR(100),
  PRIMARY KEY (fp_player_id)
  );

CREATE TABLE IF NOT EXISTS dynastr.dp_player_ranks (
player_first_name  VARCHAR(150),
player_last_name  VARCHAR(150),
player_full_name  VARCHAR(150),
fp_player_id  VARCHAR(150),
player_position  VARCHAR(150),
team  VARCHAR(150),
age  VARCHAR(150),
one_qb_rank_ecr  VARCHAR(150),
sf_player_ecr_delta  VARCHAR(150),
ecr_pos  VARCHAR(150),
one_qb_value  integer,
sf_value  integer,
insert_date  VARCHAR(150),
PRIMARY KEY (player_full_name)
);

CREATE TABLE IF NOT EXISTS dynastr.fc_player_ranks (
player_first_name  VARCHAR(150),
player_last_name  VARCHAR(150),
player_full_name  VARCHAR(150),
fc_player_id  VARCHAR(150),
mfl_player_id  VARCHAR(150),
sleeper_player_id  VARCHAR(150),
player_position  VARCHAR(150),
rank_type VARCHAR(150),
one_qb_overall_rank  VARCHAR(150),
one_qb_position_rank  VARCHAR(150),
one_qb_value integer,
one_qb_trend_30_day integer,
sf_overall_rank  VARCHAR(150),
sf_position_rank  VARCHAR(150),
sf_value integer,
sf_trend_30_day integer,
insert_date  VARCHAR(150),
PRIMARY KEY (player_full_name, rank_type)
);


CREATE TABLE IF NOT EXISTS dynastr.draft_positions (
    season VARCHAR(75),
    rounds VARCHAR(75),
    position VARCHAR(75),
    position_name VARCHAR(75),
    roster_id VARCHAR(75),
    user_id VARCHAR(75),
    league_id VARCHAR(75),
    draft_id VARCHAR(75),
    draft_set_flg VARCHAR(75),
    PRIMARY KEY (season, rounds, position, user_id, league_id)
);

CREATE TABLE IF NOT EXISTS dynastr.draft_picks (
    year VARCHAR(75),
    round VARCHAR(75),
    round_name VARCHAR(75),
    roster_id VARCHAR(75),
    owner_id VARCHAR(75),
    league_id VARCHAR(75),
    draft_id VARCHAR(75),
    session_id VARCHAR(75),
    PRIMARY KEY (year, round, roster_id,owner_id, league_id, session_id)
);

CREATE TABLE IF NOT EXISTS dynastr.player_trades (
    transaction_id VARCHAR(75),
    status_updated INTEGER,
    roster_id VARCHAR(75),
    transaction_type VARCHAR(75),
    player_id VARCHAR(75),
    league_id VARCHAR(75)
);

CREATE TABLE IF NOT EXISTS dynastr.draft_pick_trades (
    transaction_id VARCHAR(75),
    status_updated integer,
    roster_id VARCHAR(75),
    transaction_type VARCHAR(75),
    season VARCHAR(75),
    round VARCHAR(75),
    round_suffix VARCHAR(75),
    org_owner_id VARCHAR(75),
    league_id VARCHAR(75)
);

CREATE TABLE IF NOT EXISTS dynastr.managers (
    source VARCHAR(75),
    user_id  VARCHAR(75),
    league_id VARCHAR(75),
    avatar VARCHAR(75),
    display_name VARCHAR(75),
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS dynastr.nfl_player_projections (
  player_first_name VARCHAR(150),
  player_last_name VARCHAR(150),
  player_full_name VARCHAR(150),
  nfl_player_id VARCHAR(150),
  slug VARCHAR(150),
  total_projection INTEGER,
  insert_date VARCHAR(75),
  PRIMARY KEY (nfl_player_id)
);

CREATE TABLE IF NOT EXISTS dynastr.fp_player_projections (
  player_first_name VARCHAR(150),
  player_last_name VARCHAR(150),
  player_full_name VARCHAR(150),
  total_projection INTEGER,
  insert_date VARCHAR(75),
  PRIMARY KEY (player_full_name)
);

create table if not exists dynastr.user_meta (
	session_id VARCHAR(150),
	ip_address VARCHAR(150),
	agent VARCHAR(350),
	host VARCHAR(350),
	referrer VARCHAR(350)
); 

create table if not exists history.user_geo_meta (
	session_id VARCHAR(150),
	ip_address VARCHAR(150),
	city VARCHAR(150),
  region VARCHAR(150),
	country VARCHAR(150),
	hostname VARCHAR(350),
	lat VARCHAR(150),
	lng VARCHAR(150),
	org VARCHAR(150),
	postal VARCHAR(150),
	agent VARCHAR(350),
	host VARCHAR(350),
	referrer VARCHAR(350),
	insert_date VARCHAR(150),
  PRIMARY KEY (session_id)
)
INSERT INTO history.user_geo_meta VALUES ('test',Null,Null,Null,Null,Null,Null,Null,Null,Null,Null,Null,Null,'2021-08-20T23:59:00.761669')

CREATE TABLE IF NOT EXISTS history.managers (LIKE dynastr.managers INCLUDING ALL);
CREATE TABLE IF NOT EXISTS history.current_leagues (LIKE dynastr.current_leagues INCLUDING ALL);
