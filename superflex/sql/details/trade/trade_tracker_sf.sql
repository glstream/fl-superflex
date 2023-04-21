SELECT * 
                    from 
                    (select
                    league_id
                    , transaction_id
                    , status_updated
                    , user_id
                    , transaction_type
                    , asset
                    , value
                    , display_name
                    , player_id as sleeper_id
                    , _position
                    , sum(value) OVER (partition by transaction_id, user_id) as owner_total
                    , sum(value) OVER (partition by transaction_id) as deal_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , p.full_name player_name
                                    , coalesce(sf.league_type, 0) as value
                                    , m.display_name
                                    , p.player_id
                                    , p.player_position as  _position
                                    from dynastr.player_trades pt
                                    inner join dynastr.players p on pt.player_id = p.player_id
                                    left join dynastr.sf_player_ranks sf on sf.player_full_name = p.full_name
                                    inner join dynastr.draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join dynastr.managers m on cast(dp.user_id as varchar) = cast(m.user_id as varchar)
                                    where 1=1
                                    and pt.league_id = 'league_id' 
                                    and transaction_type = 'add'
                                    
                                    UNION ALL
                                    
                                    select a1.league_id
                                    ,a1.transaction_id
                                    ,a1.status_updated
                                    , a1.user_id
                                    , a1.transaction_type
                                    , asset
                                    , player_name
                                    , coalesce(sf.league_type,0) as value
                                    , m.display_name
                                    , null as player_id
                                    ,'' as _position
                                            from 
                                                ( select 
                                                dpt.league_id
                                                , transaction_id
                                                , status_updated
                                                , dp.user_id
                                                , dpt.transaction_type
                                                , CASE WHEN (ddp.position::integer) < 13 and ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                        THEN dpt.season  || ' Round ' || dpt.round || ' Pick ' || ddp.position
                                                    WHEN (ddp.position::integer) > 12 and ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                        THEN  dpt.season || ' ' || ddp.position_name || ' ' || dpt.round_suffix
                                                    ELSE dpt.season || ' Mid ' || dpt.round_suffix
                                                        END AS asset 
                                                , CASE WHEN (ddp.position::integer) < 13 and ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                        THEN dpt.season  || ' Round ' || dpt.round || ' Pick ' || ddp.position
                                                    WHEN (ddp.position::integer) > 12 and ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                        THEN  dpt.season || ' ' || ddp.position_name || ' ' || dpt.round_suffix
                                                    ELSE dpt.season || ' Mid ' || dpt.round_suffix 
                                                        END AS player_name 
                                                , dp.position_name
                                                , dpt.season
                                                , dp.draft_set_flg
                                                from dynastr.draft_pick_trades dpt
                                                inner join dynastr.draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join dynastr.draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                
                                                where 1=1  
                                                and dpt.league_id = 'league_id' 
                                                and transaction_type = 'add'
                                                --and dpt.transaction_id IN ('832101872931274752')
                                                
                                                )  a1
                                    left join dynastr.sf_player_ranks sf on a1.player_name = sf.player_full_name
                                    inner join dynastr.managers m on cast(a1.user_id as varchar) = cast(m.user_id as varchar)
                                    
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , value  desc) t2
                                    where t2.num_managers > 1
                                    order by t2.status_updated desc