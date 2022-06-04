-- Initialize the database.
-- Drop any existing data and create empty tables.

-- DROP TABLE IF EXISTS players;
DROP TABLE IF EXISTS owned_players;
DROP TABLE IF EXISTS leagues;
DROP TABLE IF EXISTS current_leagues;
-- DROP TABLE IF EXISTS ktc_player_ranks; 
-- DROP TABLE IF EXISTS espn_player_projections;  
-- DROP TABLE IF EXISTS fp_player_ranks;
DROP TABLE IF EXISTS league_players;
DROP TABLE IF EXISTS draft_positions;
DROP TABLE IF EXISTS draft_picks;
DROP TABLE IF EXISTS player_trades;
DROP TABLE IF EXISTS draft_pick_trades; 
DROP TABLE IF EXISTS managers;

CREATE TABLE IF NOT EXISTS players (
  player_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  position TEXT NOT NULL,
  age TEXT,
  team TEXT,
  search_rank TEXT
);

CREATE TABLE leagues (
  user_id TEXT NOT NULL,
  user_name TEXT,
  league_id TEXT,
  league_name TEXT,
  insert_date TEXT,
  PRIMARY KEY (user_id, league_id)
);

CREATE TABLE owned_players (
  session_id TEXT NOT NULL, 
  owner_league_id TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  player_id TEXT,
  league_id TEXT NOT NULL,
  user_id TEXT,
  insert_date TEXT
);

CREATE TABLE league_players (
  session_id TEXT NOT NULL, 
  owner_user_id TEXT NOT NULL,
  player_id TEXT  NOT NULL,
  league_id TEXT NOT NULL,
  user_id TEXT  NOT NULL,
  insert_date TEXT,
  PRIMARY KEY (user_id, player_id)
);

CREATE TABLE current_leagues (
  session_id NOT NULL,
  user_id TEXT NOT NULL,
  user_name TEXT,
  league_id TEXT,
  league_name TEXT,
  avatar TEXT,
  total_rosters NUMBER,
  insert_date TEXT,
  PRIMARY KEY (session_id, league_id)
);

CREATE TABLE IF NOT EXISTS ktc_player_ranks (
  player_name NOT NULL,
  ktc_player_id TEXT NOT NULL,
  slug TEXT,
  position TEXT,
  position_id TEXT,
  team TEXT,
  rookie TEXT,
  college TEXT,
  age TEXT,
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
  insert_date TEXT,
  PRIMARY KEY (ktc_player_id)
);

CREATE TABLE IF NOT EXISTS espn_player_projections (
  player_name NOT NULL,
  espn_player_id TEXT NOT NULL,
  ppr_rank INT,
  ppr_auction_value INT,
  total_projection INT,
  recs INT,
  rec_yards INT,
  rec_tds INT,
  carries INT,
  rush_yards INT,
  rush_tds INT,
  pass_attempts INT,
  pass_completions INT,
  pass_yards INT,
  pass_tds INT,
  pass_ints INT,
  insert_date TEXT,
  PRIMARY KEY (espn_player_id)
);

CREATE TABLE IF NOT EXISTS fp_player_ranks (
  player_name TEXT NOT NULL,
  fp_player_id TEXT NOT NULL,
  player_team_id TEXT,
  player_position_id TEXT,
  player_positions TEXT,
  player_short_name TEXT,
  player_eligibility TEXT,
  player_yahoo_positions TEXT,
  player_page_url TEXT, 
  player_square_image_url TEXT,
  player_image_url TEXT,
  player_yahoo_id TEXT, 
  cbs_player_id TEXT,
  player_bye_week TEXT, 
  player_age TEXT,
  player_ecr_delta TEXT,
  rank_ecr TEXT,
  rank_min TEXT,
  rank_max TEXT,
  rank_ave TEXT,
  rank_std TEXT, 
  pos_rank TEXT,
  tier TEXT,
  insert_date TEXT,
  PRIMARY KEY (fp_player_id)
  );

CREATE TABLE IF NOT EXISTS draft_positions (
    season TEXT,
    rounds TEXT,
    position TEXT,
    position_name TEXT,
    roster_id TEXT,
    user_id TEXT,
    league_id TEXT,
    draft_id TEXT,
    PRIMARY KEY (season, rounds, position, user_id, league_id)
);

CREATE TABLE IF NOT EXISTS draft_picks (
    year TEXT,
    round TEXT,
    round_name TEXT,
    roster_id TEXT,
    owner_id TEXT,
    league_id TEXT,
    draft_id TEXT,
    session_id TEXT,
    PRIMARY KEY (year, round, roster_id,owner_id, league_id, session_id)
);

CREATE TABLE IF NOT EXISTS player_trades (
    transaction_id text,
    status_updated int,
    roster_id text,
    transaction_type text,
    player_id text,
    league_id text
);

CREATE TABLE IF NOT EXISTS draft_pick_trades (
    transaction_id text,
    status_updated number,
    roster_id text,
    transaction_type text,
    season text,
    round text,
    round_suffix text, 
    org_owner_id text,
    league_id text
);

CREATE TABLE IF NOT EXISTS managers (
    source text,
    user_id number,
    league_id text,
    avatar text,
    display_name text,
    PRIMARY KEY (user_id)
);
    