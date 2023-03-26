WITH base_players as (SELECT
                    lp.user_id
                    , lp.league_id
                    , lp.session_id
                    , pl.player_id
                    , ktc.ktc_player_id
                    , pl.player_position
                    , coalesce(ktc.league_type, -1) as player_value
                    , RANK() OVER (PARTITION BY lp.user_id, pl.player_position ORDER BY coalesce(ktc.league_type, -1) desc) as player_order
                    , qb_cnt
                    , rb_cnt
                    , wr_cnt
                    , te_cnt
                    , flex_cnt
                    , sf_cnt
                    , rf_cnt

                    FROM dynastr.league_players lp
                    INNER JOIN dynastr.players pl on lp.player_id = pl.player_id
                    LEFT JOIN dynastr.ktc_player_ranks ktc on concat(pl.first_name, pl.last_name)  = concat(ktc.player_first_name, ktc.player_last_name)
                    INNER JOIN dynastr.current_leagues cl on lp.league_id = cl.league_id and cl.session_id = 'session_id' 
                    WHERE lp.session_id = 'session_id'
                    and lp.league_id = 'league_id'
                    and pl.player_position IN ('QB', 'RB', 'WR', 'TE' ))

                    , base_picks as (SELECT t1.user_id
                                , t1.season
                                , t1.year
                                , t1.player_full_name
                                , ktc.ktc_player_id
                                FROM (
                                    SELECT  
                                    al.user_id
                                    , al.season
                                    , al.year 
                                    , CASE WHEN (dname.position::integer) < 13 and al.draft_set_flg = 'Y' and al.year = dname.season
                                                THEN al.year || ' Round ' || al.round || ' Pick ' || dname.position
                                            WHEN (dname.position::integer) > 12 and al.draft_set_flg = 'Y' and al.year = dname.season
                                                THEN al.year || ' ' || dname.position_name || ' ' || al.round_name 
                                            ELSE al.year|| ' Mid ' || al.round_name 
                                            END AS player_full_name 
                                    FROM (                           
                                        SELECT dp.roster_id
                                        , dp.year
                                        , dp.round_name
                                        , dp.round
                                        , dp.league_id
                                        , dpos.user_id
                                        , dpos.season
                                        , dpos.draft_set_flg
                                        FROM dynastr.draft_picks dp
                                        INNER JOIN dynastr.draft_positions dpos on dp.owner_id = dpos.roster_id and dp.league_id = dpos.league_id

                                        WHERE dpos.league_id = 'league_id'
                                        and dp.session_id = 'session_id'
                                        ) al 
                                    INNER JOIN dynastr.draft_positions dname on  dname.roster_id = al.roster_id and al.league_id = dname.league_id
                                ) t1
                                LEFT JOIN dynastr.ktc_player_ranks ktc on t1.player_full_name = ktc.player_full_name
                                    )						   
                    , starters as (SELECT  
                    qb.user_id
                    , qb.player_id
                    , qb.ktc_player_id
                    , qb.player_position
                    , qb.player_position as fantasy_position
                    , qb.player_order
                    from base_players qb
                    where 1=1
                    and qb.player_position = 'QB'
                    and qb.player_order <= qb.qb_cnt
                    UNION ALL
                    SELECT 
                    rb.user_id
                    , rb.player_id
                    , rb.ktc_player_id
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
                    , wr.ktc_player_id
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
                    , te.ktc_player_id
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
                    , ns.ktc_player_id
                    , ns.player_position
                    , 'FLEX' as fantasy_position
                    , ns.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.flex_cnt
                    from base_players fp
                    left join starters s on s.ktc_player_id = fp.ktc_player_id
                    where 1=1
                    and s.ktc_player_id IS NULL
                    and fp.player_position IN ('RB','WR','TE')  
                    order by player_order) ns
                    where player_order <= ns.flex_cnt)

                    ,super_flex as (
                    SELECT
                    ns_sf.user_id
                    , ns_sf.player_id
                    , ns_sf.ktc_player_id
                    , ns_sf.player_position
                    , 'SUPER_FLEX' as fantasy_position
                    , ns_sf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , RANK() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , fp.sf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.ktc_player_id = fp.ktc_player_id
                    where s.ktc_player_id IS NULL
                    and fp.player_position IN ('QB','RB','WR','TE')  
                    order by player_order) ns_sf
                    where player_order <= ns_sf.sf_cnt)

                    ,rec_flex as (
                    SELECT
                    ns_rf.user_id
                    , ns_rf.player_id
                    , ns_rf.ktc_player_id
                    , ns_rf.player_position
                    , 'REC_FLEX' as fantasy_position
                    , ns_rf.player_order
                    from (
                    SELECT
                    fp.user_id
                    , fp.ktc_player_id
                    , fp.player_id
                    , fp.player_position
                    , ROW_NUMBER() OVER (PARTITION BY fp.user_id ORDER BY fp.player_value desc) as player_order
                    , rf_cnt
                    from base_players fp
                    left join (select * from starters UNION ALL select * from flex) s on s.ktc_player_id = fp.ktc_player_id
                    where s.ktc_player_id IS NULL
                    and fp.player_position IN ('WR','TE')  
                    order by player_order) ns_rf
                    where player_order <= ns_rf.rf_cnt)

                    , all_starters as (select 
                    user_id
                    ,ap.player_id
                    ,ap.ktc_player_id
                    ,ap.player_position 
                    ,ap.fantasy_position
                    ,'STARTER' as fantasy_designation
                    ,ap.player_order
                    from (select * from starters UNION ALL select * from flex UNION ALL select * from super_flex UNION ALL select * from rec_flex) ap
                    order by user_id, player_position desc)
                                            
                    SELECT tp.user_id
                    ,m.display_name
                    ,coalesce(ktc.player_full_name, tp.picks_player_name, p.full_name) as full_name
                    , tp.draft_year
                    ,ktc.slug as hyper_link
                    ,p.team
                    ,tp.player_id as sleeper_id
                    ,tp.player_position
                    ,tp.fantasy_position
                    ,tp.fantasy_designation
                    ,coalesce(ktc.league_type, -1) as player_value
                    ,coalesce(ktc.positional_rank, -1) as player_rank
                    from (select 
                            user_id
                            ,ap.player_id
                            ,ap.ktc_player_id
                            ,NULL as picks_player_name
                            ,NULL as draft_year
                            ,ap.player_position 
                            ,ap.fantasy_position
                            ,'STARTER' as fantasy_designation
                            ,ap.player_order 
                            from all_starters ap
                            UNION
                            select 
                            bp.user_id
                            ,bp.player_id
                            ,bp.ktc_player_id
                            ,NULL as picks_player_name
                            ,NULL as draft_year
                            ,bp.player_position 
                            ,bp.player_position as fantasy_position
                            ,'BENCH' as fantasy_designation
                            ,bp.player_order
                            from base_players bp where bp.player_id not in (select player_id from all_starters)
                            UNION ALL
                            select 
                            user_id
                            ,null as player_id
                            ,picks.ktc_player_id
                            ,picks.player_full_name as picks_player_name
                            ,picks.year as draft_year
                            ,'PICKS' as player_position 
                            ,'PICKS' as fantasy_position
                            ,'PICKS' as fantasy_designation
                            , null as player_order
                            from base_picks picks
                            order by picks_player_name asc
                            ) tp
                    left join dynastr.players p on tp.player_id = p.player_id
                    LEFT JOIN dynastr.ktc_player_ranks ktc on tp.ktc_player_id = ktc.ktc_player_id
                    inner join dynastr.managers m on tp.user_id = m.user_id 
                    order by draft_year asc, player_value desc