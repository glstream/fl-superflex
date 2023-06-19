SELECT
                    t3.user_id
                    , t3.display_name
                    , round(total_value)::int as total_value
                    , ROW_NUMBER() OVER (order by sum(position_value) desc) total_rank 
                    , NTILE(10) OVER (order by total_value desc) total_tile
                    , max(qb_value) as qb_value
                    , RANK() OVER (order by sum(qb_value) desc) qb_rank
                    , NTILE(10) OVER (order by sum(qb_value) desc) qb_tile
                    , sum(qb_value) as qb_sum
					, coalesce(round(sum(qb_value::integer) / NULLIF(sum(qb_count), 0),0), 0) as qb_average
					, sum(qb_count) as qb_count
                    , max(rb_value) as rb_value
                    , RANK() OVER (order by sum(rb_value::integer) desc) rb_rank
                    , NTILE(10) OVER (order by sum(rb_value::integer) desc) rb_tile
                    , sum(rb_value) as rb_sum
					, coalesce(round(sum(rb_value::integer) / NULLIF(sum(rb_count), 0),0), 0) as rb_average
					, sum(rb_count) as rb_count
                    , max(wr_value) as wr_value
                    , RANK() OVER (order by sum(wr_value) desc) wr_rank
                    , NTILE(10) OVER (order by sum(wr_value) desc) wr_tile
                    , sum(wr_value) as wr_sum
					, coalesce(round(sum(wr_value::integer) / NULLIF(sum(wr_count), 0),0), 0) as wr_average
					, sum(wr_count) as wr_count
                    , max(te_value) as te_value
                    , RANK() OVER (order by sum(te_value) desc) te_rank
                    , NTILE(10) OVER (order by sum(te_value) desc) te_tile
                    , sum(te_value) as te_sum
					, coalesce(round(sum(te_value::integer) / NULLIF(sum(te_count), 0),0), 0) as te_average
					, sum(te_count) as wr_count
                    , max(flex_value) as flex_value
                    , RANK() OVER (order by sum(flex_value) desc) flex_rank
                    , max(super_flex_value) as super_flex_value
                    , RANK() OVER (order by sum(super_flex_value) desc) super_flex_rank
					, max(starters_value) as starters_value
                    , RANK() OVER (order by sum(starters_value) desc) starters_rank
                    , NTILE(10) OVER (order by sum(starters_value) desc) starters_tile
                    , sum(starters_value) as starters_sum
					, coalesce(round(sum(starters_value::integer) / NULLIF(sum(starters_count), 0),0), 0) as starters_average
					, sum(starters_count) as starters_count
					, max(Bench_value) as Bench_value
                    , RANK() OVER (order by sum(bench_value) desc) bench_rank
                    , NTILE(10) OVER (order by sum(bench_value) desc) bench_tile
                    , sum(bench_value) as bench_sum
					, coalesce(round(sum(bench_value::integer) / NULLIF(sum(bench_count), 0),0), 0) as bench_average
					, sum(bench_count) as bench_count


                    from (select 
                        user_id
                    ,display_name
                    , sum(player_value) as position_value
                    , total_value
                    , DENSE_RANK() OVER (PARTITION BY fantasy_position  order by sum(player_value) desc) position_rank
                    , DENSE_RANK() OVER (order by total_value desc) total_rank
                    , fantasy_position
                    , case when player_position = 'QB' THEN sum(player_value) else 0 end as qb_value
                    , case when player_position = 'QB' THEN count(full_name) else 0 end as qb_count
                    , case when player_position = 'RB' THEN sum(player_value) else 0 end as rb_value
                    , case when player_position = 'RB' THEN count(full_name) else 0 end as rb_count
                    , case when player_position = 'WR' THEN sum(player_value) else 0 end as wr_value
                    , case when player_position = 'WR' THEN count(full_name) else 0 end as wr_count
                    , case when player_position = 'TE' THEN sum(player_value) else 0 end as te_value
                    , case when player_position = 'TE' THEN count(full_name) else 0 end as te_count
                    , case when fantasy_position = 'FLEX' THEN sum(player_value) else 0 end as flex_value
                    , case when fantasy_position = 'SUPER_FLEX' THEN sum(player_value) else 0 end as super_flex_value
                    , case when fantasy_designation = 'STARTER' THEN sum(player_value) else 0 end as starters_value
                    , case when fantasy_designation = 'STARTER' THEN count(full_name) else 0 end as starters_count
                    , case when fantasy_designation = 'BENCH' THEN sum(player_value) else 0 end as bench_value
                    , case when fantasy_designation = 'BENCH' THEN count(full_name) else 0 end as bench_count
                     from 
                    (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    from (WITH base_players as (SELECT
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
order by m.display_name, player_value desc) all_players
									 					) t2
                                                group by 
                                                  t2.user_id
                                                , t2.display_name
                                                , t2.total_value
                                                , t2.fantasy_position
                                                , t2.player_position
                                                , t2.fantasy_designation ) t3
                                                 group by 
                                                t3.user_id
                                                , t3.display_name
                                                , total_value
                                                , total_rank
                                                order by
                                                total_value desc