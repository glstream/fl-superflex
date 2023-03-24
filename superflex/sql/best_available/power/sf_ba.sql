SELECT 
ba_t1.player_id as sleeper_id
, ba_t1.full_name
, ba_t1.player_position
, coalesce(ba_t1.player_value,0) as player_value
from (SELECT
pl.player_id
,pl.full_name
,pl.player_position
, sf.league_type as player_value
, ROW_NUMBER() OVER(PARTITION BY pl.player_position ORDER BY sf.league_type desc) rn

FROM dynastr.players pl 
INNER JOIN dynastr.sf_player_ranks sf on sf.player_full_name  = pl.full_name
where 1=1 
and pl.player_id NOT IN (SELECT
                lp.player_id
                from dynastr.league_players lp
                where lp.session_id = 'session_id'
                and lp.league_id = 'league_id'
            )
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' )
and pl.team is not null
order by player_value desc) ba_t1
where ba_t1.rn <= 4
order by ba_t1.player_position, ba_t1.player_value desc