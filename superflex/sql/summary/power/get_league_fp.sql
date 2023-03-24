with base as (SELECT 
user_id
, display_name
, player_position
, avg_position_value
, position_cnt
, avg_value
, total_value
, case when player_position = 'QB' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as qb_avg_rank
, case when player_position = 'QB' then total_position_value end as qb_total_value
, case when player_position = 'RB' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as rb_avg_rank
, case when player_position = 'RB' then total_position_value end as rb_total_value
, case when player_position = 'WR' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as wr_avg_rank
, case when player_position = 'WR' then total_position_value end as wr_total_value
, case when player_position = 'TE' then DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) end as te_avg_rank
, case when player_position = 'TE' then total_position_value end as te_total_value
, case when fantasy_designation = 'BENCH' then DENSE_RANK() OVER (PARTITION BY fantasy_designation order by avg_fantasy_value asc) end as bench_avg_rank
, case when fantasy_designation = 'BENCH' then total_fasntasy_value end as bench_total_value
, case when fantasy_designation = 'STARTER' then DENSE_RANK() OVER (PARTITION BY fantasy_designation order by avg_fantasy_value asc) end as starters_avg_rank
, case when fantasy_designation = 'STARTER' then total_fasntasy_value end as starter_total_value

, DENSE_RANK() OVER (PARTITION BY player_position order by avg_position_value asc) position_rank
from (select all_players.user_id 
                    , all_players.display_name 
                    , all_players.full_name
                    , all_players.player_position
                    , all_players.fantasy_position
                    , all_players.fantasy_designation
                    , all_players.team
                    , all_players.player_value
                    , sum(all_players.player_value) OVER (PARTITION BY all_players.user_id) as total_value  
                    , avg(all_players.player_value) OVER (PARTITION BY all_players.user_id) as avg_value 
	  			    , count(all_players.full_name) OVER (PARTITION BY all_players.user_id, all_players.player_position) as position_cnt 
					, avg(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.player_position) as avg_position_value
	  				, sum(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.player_position) as total_position_value
	  				, avg(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.fantasy_designation) as avg_fantasy_value 
	  				, sum(all_players.player_value) OVER (PARTITION BY all_players.user_id, all_players.fantasy_designation) as total_fasntasy_value
                    from (with base_players as (SELECT
                        lp.user_id
                        , lp.league_id
                        , lp.session_id
                        , pl.full_name 
                        , pl.player_id
                        , fp.fp_player_id
                        , pl.player_position
                        , coalesce(fp.lt_rank_ecr, 529) as player_value
                        , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(fp.lt_rank_ecr, 529) asc) as player_order
                        , qb_cnt
                        , rb_cnt
                        , wr_cnt
                        , te_cnt
                        , flex_cnt
                        , sf_cnt
                        , rf_cnt

                        from dynastr.league_players lp
                        inner join dynastr.players pl on lp.player_id = pl.player_id
                        LEFT JOIN dynastr.fp_player_ranks fp on concat(pl.first_name, pl.last_name) = concat(fp.player_first_name, fp.player_last_name)
                        inner join dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = 'session_id'
                        where lp.session_id = 'session_id'
                        and lp.league_id = 'league_id'
                        and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))   

                        , starters as (select  
                        qb.user_id
                        , qb.player_id
                        , qb.fp_player_id
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
                        , rb.fp_player_id
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
                        , wr.fp_player_id
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
                        , te.fp_player_id
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
                        , ns.fp_player_id
                        , ns.player_position
                        , 'FLEX' as fantasy_position
                        , ns.player_order
                        from (
                        SELECT
                        fp.user_id
                        , fp.fp_player_id
                        , fp.player_id
                        , fp.player_position
                        , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
                        , fp.flex_cnt
                        from base_players fp
                        left join starters s on s.fp_player_id = fp.fp_player_id
                        where 1=1
                        and s.fp_player_id IS NULL
                        and fp.player_position IN ('RB','WR','TE')  
                        order by player_order) ns
                        where player_order <= ns.flex_cnt)

                        ,super_flex as (
                        SELECT
                        ns_sf.user_id
                        , ns_sf.player_id
                        , ns_sf.fp_player_id
                        , ns_sf.player_position
                        , 'SUPER_FLEX' as fantasy_position
                        , ns_sf.player_order
                        from (
                        SELECT
                        fp.user_id
                        , fp.fp_player_id
                        , fp.player_id
                        , fp.player_position
                        , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value asc) as player_order
                        , fp.sf_cnt
                        from base_players fp
                        left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
                        where s.fp_player_id IS NULL
                        and fp.player_position IN ('QB','RB','WR','TE')  
                        order by player_order) ns_sf
                        where player_order <= ns_sf.sf_cnt)

                        ,rec_flex as (
                        SELECT
                        ns_rf.user_id
                        , ns_rf.player_id
                        , ns_rf.fp_player_id
                        , ns_rf.player_position
                        , 'REC_FLEX' as fantasy_position
                        , ns_rf.player_order
                        from (
                        SELECT
                        fp.user_id
                        , fp.fp_player_id
                        , fp.player_id
                        , fp.player_position
                        , ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                        , rf_cnt
                        from base_players fp
                        left join (select * from starters UNION ALL select * from flex) s on s.fp_player_id = fp.fp_player_id
                        where s.fp_player_id IS NULL
                        and fp.player_position IN ('WR','TE')  
                        order by player_order) ns_rf
                        where player_order <= ns_rf.rf_cnt)

                        , all_starters as (select 
                        user_id
                        ,ap.player_id
                        ,ap.fp_player_id
                        ,ap.player_position 
                        ,ap.fantasy_position
                        ,'STARTER' as fantasy_designation
                        ,ap.player_order
                        from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex UNION ALL select * from rec_flex) ap
                        order by user_id, player_position asc)
                                                
                        select tp.user_id
                        ,m.display_name
                        ,p.full_name
                        ,p.team
                        ,tp.player_id as sleeper_id
                        ,tp.player_position
                        ,tp.fantasy_position
                        ,tp.fantasy_designation
                        ,fp.sf_rank_ecr as player_value
                        from (select 
                                user_id
                                ,ap.player_id
                                ,ap.fp_player_id
                                ,ap.player_position 
                                ,ap.fantasy_position
                                ,'STARTER' as fantasy_designation
                                ,ap.player_order 
                                from all_starters ap
                                UNION
                                select 
                                bp.user_id
                                ,bp.player_id
                                ,bp.fp_player_id
                                ,bp.player_position 
                                ,bp.player_position as fantasy_position
                                ,'BENCH' as fantasy_designation
                                ,bp.player_order
                                from base_players bp where bp.player_id not in (select player_id from all_starters)) tp
                        inner join dynastr.players p on tp.player_id = p.player_id
                        inner join dynastr.fp_player_ranks fp on tp.fp_player_id = fp.fp_player_id
                        inner join dynastr.managers m on tp.user_id = m.user_id 
                        order by m.display_name, player_value asc) all_players)
						t1 
						group by 
						user_id
						,display_name
						,player_position
			  			,fantasy_designation
						,avg_position_value
			            ,avg_fantasy_value
						,position_cnt
						,avg_value
						,total_value
			  			,total_position_value
			  			,total_fasntasy_value
			 )
	
SELECT 
base.user_id
,display_name 
,total_value
,round(avg_value) as total_avg
,RANK() OVER (order by total_value asc) total_rank
,NTILE(10) OVER (order by total_value asc) total_tile
,RANK() OVER (order by avg_value asc) avg_rank
,NTILE(10) OVER (order by avg_value asc) avg_tile 
,qb_avg_rank
,NTILE(10) OVER (order by qb_avg_rank asc) qb_avg_tile
,qb_total_value
,rb.rb_avg_rank
,NTILE(10) OVER (order by rb.rb_avg_rank asc) rb_avg_tile
,rb.rb_total_value
,wr.wr_avg_rank
,NTILE(10) OVER (order by wr.wr_avg_rank asc) wr_avg_tile
,wr.wr_total_value
,te.te_avg_rank
,NTILE(10) OVER (order by te.te_avg_rank asc) te_avg_tile
,te.te_total_value
,bench.bench_avg_rank
,NTILE(10) OVER (order by bench.bench_avg_rank asc) bench_avg_tile
,bench.bench_total_value
,starter.starters_avg_rank 
,NTILE(10) OVER (order by starter.starters_avg_rank asc) starters_avg_tile
,starter.starter_total_value
from base
inner join (SELECT user_id ,rb_avg_rank, rb_total_value from base where rb_avg_rank is not null) rb on base.user_id = rb.user_id
inner join (SELECT user_id ,wr_avg_rank, wr_total_value from base where wr_avg_rank is not null) wr on base.user_id = wr.user_id
inner join (SELECT user_id ,te_avg_rank, te_total_value from base where te_avg_rank is not null) te on base.user_id = te.user_id
inner join (SELECT user_id ,bench_avg_rank, bench_total_value from base where bench_avg_rank is not null) bench on base.user_id = bench.user_id
inner join (SELECT user_id ,starters_avg_rank, starter_total_value from base where starters_avg_rank is not null) starter on base.user_id = starter.user_id

where qb_avg_rank is not null 
group by
base.user_id
,display_name 
,total_value
,avg_value
,qb_avg_rank
,qb_total_value
,rb.rb_avg_rank
,rb.rb_total_value
,wr.wr_avg_rank
,wr.wr_total_value
,te.te_avg_rank
,te.te_total_value
,bench.bench_avg_rank
,bench.bench_total_value
,starter.starters_avg_rank
,starter.starter_total_value
order by 
total_avg asc