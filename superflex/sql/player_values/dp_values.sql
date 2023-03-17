with dp_players as (select player_full_name
, team					
, age
, sf_value as value
, fc.player_position as _position
, 'sf_value' as _rank_type 
, insert_date
from dynastr.dp_player_ranks fc
where 1=1
and sf_value is not null
and player_full_name not like '%2022%'					
UNION ALL
select player_full_name
, team					
, age
, one_qb_value as value
, fc.player_position as _position
, 'one_qb_value' as _rank_type 
, insert_date
from dynastr.dp_player_ranks fc 
where 1=1
and one_qb_value is not null 
and player_full_name not like '%2022%'
)
															   
select player_full_name
,CONCAT(_position, ' ', rank() OVER (partition by _rank_type, _position ORDER BY value DESC)) as pos_rank
, team
, age
, value
, _position
, _rank_type
, TO_DATE(insert_date, 'YYYY-mm-DDTH:M:SS.z')-1 as _insert_date
from dp_players