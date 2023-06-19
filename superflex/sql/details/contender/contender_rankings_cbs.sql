WITH base_players as (SELECT
lp.user_id
, lp.league_id
, lp.session_id
, pl.full_name 
, pl.player_id
, ep.player_full_name
, pl.player_position
, coalesce(ep.total_projection, -1) as player_value
, ROW_NUMBER() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ep.total_projection, -1) desc) as player_order
, qb_cnt
, rb_cnt
, wr_cnt
, te_cnt
, flex_cnt
, sf_cnt
, rf_cnt

from dynastr.league_players lp
inner join dynastr.players pl on lp.player_id = pl.player_id
LEFT JOIN dynastr.cbs_player_projections ep on concat(pl.first_name, pl.last_name)  = concat(ep.player_first_name, ep.player_last_name)
inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = 'session_id'
where lp.session_id = 'session_id'
and lp.league_id = 'league_id'
and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))  
						   
, starters as (SELECT  
qb.user_id
, qb.player_id
, qb.player_full_name
, qb.player_position
, qb.player_position as fantasy_position
, qb.player_order
from base_players qb
where 1=1
and qb.player_position = 'QB'
and qb.player_order <= qb.qb_cnt
UNION ALL
select 
rb.user_id
, rb.player_id
, rb.player_full_name
, rb.player_position
, rb.player_position as fantasy_position
, rb.player_order
from base_players rb
where 1=1
and rb.player_position = 'RB'
and rb.player_order <= rb.rb_cnt
UNION ALL
select 
wr.user_id
, wr.player_id
, wr.player_full_name
, wr.player_position
, wr.player_position as fantasy_position
, wr.player_order
from base_players wr
where wr.player_position = 'WR'
and wr.player_order <= wr.wr_cnt

UNION ALL
select 
te.user_id
, te.player_id
, te.player_full_name
, te.player_position
, te.player_position as fantasy_position
, te.player_order
from 	
base_players te
where te.player_position = 'TE'
and te.player_order <= te.te_cnt
)

, flex as (
SELECT
ns.user_id
, ns.player_id
, ns.player_full_name
, ns.player_position
, 'FLEX' as fantasy_position
, ns.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.flex_cnt
from base_players fp
left join starters s on s.player_full_name = fp.player_full_name
where 1=1
and s.player_full_name IS NULL
and fp.player_position IN ('RB','WR','TE')  
order by player_order) ns
where player_order <= ns.flex_cnt)

,super_flex as (
SELECT
ns_sf.user_id
, ns_sf.player_id
, ns_sf.player_full_name
, ns_sf.player_position
, 'SUPER_FLEX' as fantasy_position
, ns_sf.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.sf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.player_full_name = fp.player_full_name
where s.player_full_name IS NULL
and fp.player_position IN ('QB','RB','WR','TE')  
order by player_order) ns_sf
where player_order <= ns_sf.sf_cnt)

,rec_flex as (
SELECT
ns_rf.user_id
, ns_rf.player_id
, ns_rf.player_full_name
, ns_rf.player_position
, 'REC_FLEX' as fantasy_position
, ns_rf.player_order
from (
SELECT
fp.user_id
, fp.player_full_name
, fp.player_id
, fp.player_position
, ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
, fp.rf_cnt
from base_players fp
left join (select * from starters UNION ALL select * from flex) s on s.player_full_name = fp.player_full_name
where s.player_full_name IS NULL
and fp.player_position IN ('WR','TE')  
order by player_order) ns_rf
where player_order <= ns_rf.rf_cnt)

, all_starters as (select 
user_id
,ap.player_id
,ap.player_full_name
,ap.player_position 
,ap.fantasy_position
,'STARTER' as fantasy_designation
,ap.player_order
from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex UNION ALL select * from rec_flex) ap
order by user_id, player_position desc)
						  
select tp.user_id
,m.display_name
,p.full_name
,lower(p.first_name) as first_name
,lower(p.last_name) as last_name
,p.team
,tp.player_full_name
,tp.player_id as sleeper_id
,tp.player_position
,tp.fantasy_position
,tp.fantasy_designation
,coalesce(ep.total_projection, -1) as player_value
from (select 
		user_id
		,ap.player_id
		,ap.player_full_name
		,ap.player_position 
		,ap.fantasy_position
		,'STARTER' as fantasy_designation
		,ap.player_order 
		from all_starters ap
		UNION
		select 
		bp.user_id
		,bp.player_id
		,bp.player_full_name
		,bp.player_position 
		,bp.player_position as fantasy_position
		,'BENCH' as fantasy_designation
		,bp.player_order
		from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
inner join dynastr.players p on tp.player_id = p.player_id
inner JOIN dynastr.cbs_player_projections ep on tp.player_full_name = ep.player_full_name

inner join dynastr.managers m on tp.user_id = m.user_id 
order by m.display_name, player_value desc