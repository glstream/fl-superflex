with fc_players as (select player_full_name
, p.team					
, p.age
, sf_value as value
, fc.player_position as _position
, 'sf_value' as _rank_type 
,fc.insert_date
from dynastr.fc_player_ranks fc
left join dynastr.players p on fc.sleeper_player_id = p.player_id
where 1=1
and rank_type = 'dynasty'
and sf_value is not null					
UNION ALL
select player_full_name
, p.team					
, p.age
, one_qb_value as value
, fc.player_position as _position
, 'one_qb_value' as _rank_type 
,fc.insert_date
from dynastr.fc_player_ranks fc 
left join dynastr.players p on fc.sleeper_player_id = p.player_id 				
where 1=1
and rank_type = 'dynasty'
and one_qb_value is not null 					
)
															   
select player_full_name
,CONCAT(_position, ' ', rank() OVER (partition by _rank_type, _position ORDER BY value DESC)) as pos_rank
, team
, age
, value
, _position
, _rank_type
, TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z')-1 as _insert_date
from fc_players