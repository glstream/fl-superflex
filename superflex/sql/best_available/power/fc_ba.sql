SELECT 
ba_t1.player_id as sleeper_id
, ba_t1.full_name
, ba_t1.player_position
, coalesce(ba_t1.player_value,0) as player_value
from (SELECT
pl.player_id
,pl.full_name
,pl.player_position
, fc.league_type as player_value
, ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY fc.league_type desc) rn

FROM dynastr.players pl 
INNER JOIN dynastr.fc_player_ranks fc on concat(pl.first_name, pl.last_name)  = concat(fc.player_first_name, fc.player_last_name)
where 1=1 
and pl.player_id NOT IN (SELECT
                lp.player_id
                from dynastr.league_players lp
                where lp.session_id = 'session_id'
                and lp.league_id = 'league_id'
            )
and rank_type = 'dynasty'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
and pl.team is not null
order by player_value desc) ba_t1
where ba_t1.rn <= 5
order by ba_t1.player_position, ba_t1.player_value desc