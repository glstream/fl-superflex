select
display_name
,trades_cnt
, NTILE(10) OVER (ORDER BY trades_cnt desc) cnt_tile
, total_add
, NTILE(10) OVER (ORDER BY total_add desc) add_tile
, total_drop
, NTILE(10) OVER (ORDER BY total_drop asc) drop_tile
, total_diff
, NTILE(10) OVER (ORDER BY total_diff desc) diff_tile
, avg_per_trade
, NTILE(10) OVER (ORDER BY avg_per_trade desc) avg_tile
from
    (SELECT display_name
                    , count(distinct transaction_id) trades_cnt
                    , sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) as total_add
                    , sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END) as total_drop
                    , sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END) total_diff
                    , (sum(CASE WHEN transaction_type = 'add' THEN value ELSE 0 END) - sum(CASE WHEN transaction_type = 'drop' THEN value ELSE 0 END))/count(distinct transaction_id) as avg_per_trade
                    
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
                    , player_id
                    , sum(value) OVER (partition by transaction_id, user_id) owner_total
                    , dense_rank() OVER (partition by transaction_id order by user_id) + dense_rank() OVER (partition by transaction_id order by user_id desc) - 1 num_managers

                    from   ( select pt.league_id
                                    , transaction_id
                                    , status_updated
                                    , dp.user_id
                                    , pt.transaction_type
                                    , p.full_name as asset
                                    , p.full_name player_name
                                    , coalesce(fc.league_type, 0) as value
                                    , m.display_name
                                    , p.player_id
                                    from dynastr.player_trades pt
                                    inner join dynastr.players p on pt.player_id = p.player_id
                                    left join dynastr.fc_player_ranks fc on concat(p.first_name, p.last_name) = concat(fc.player_first_name, fc.player_last_name)
                                    inner join dynastr.draft_positions dp on pt.roster_id = dp.roster_id and dp.league_id = pt.league_id
                                    inner join dynastr.managers m on cast(dp.user_id as varchar) = cast(m.user_id as varchar)
                                    where 1=1
                                    and pt.league_id = 'league_id' 
                                    and fc.rank_type = 'dynasty'
                                    
                                    UNION ALL
                                    
                                    select a1.league_id
                                    ,a1.transaction_id
                                    ,a1.status_updated
                                    , a1.user_id
                                    , a1.transaction_type
                                    , a1.asset as asset
                                    , a1.asset as player_name
                                    , fc.league_type as value
                                    , m.display_name
                                    , null as player_id
                                            from 
                                                ( select 
                                                dpt.league_id
                                                , transaction_id
                                                , status_updated
                                                , dp.user_id
                                                , dpt.transaction_type
                                                , CASE 
                                                    WHEN ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                    THEN ddp.season || ' Round ' || dpt.round || ' Pick ' || ddp.position
                                                    ELSE dpt.season || ' Round ' || dpt.round
                                                    END AS asset
                                                 , CASE 
                                                    WHEN ddp.draft_set_flg = 'Y' and dpt.season = ddp.season 
                                                    THEN ddp.season || ' Round ' || dpt.round || ' Pick ' || ddp.position
                                                    ELSE dpt.season || ' Round ' || dpt.round
                                                    END AS player_name
                                                , dp.position_name
                                                , dpt.season
                                                from dynastr.draft_pick_trades dpt
                                                inner join dynastr.draft_positions dp on dpt.roster_id = dp.roster_id and dpt.league_id = dp.league_id
                                                inner join dynastr.draft_positions ddp on dpt.org_owner_id = ddp.roster_id and dpt.league_id = ddp.league_id
                                                where 1=1  
                                                and dpt.league_id = 'league_id' 
                                                
                                                )  a1
                                    inner join dynastr.fc_player_ranks fc on a1.player_name = fc.player_full_name
                                    inner join dynastr.managers m on cast(a1.user_id as varchar) = cast(m.user_id as varchar)
                                    where fc.rank_type = 'dynasty'
                                    ) t1                              
                                    order by 
                                    status_updated desc
                                    , value  desc) t2
                                    where t2.num_managers > 1
                    group by display_name
                    order by trades_cnt desc)t3