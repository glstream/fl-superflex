with ktc_players as (select player_full_name
,  team
, case when round(CAST(age AS float)) < 1 then Null else round(CAST(age AS float)) end as age
, sf_value as value
, sf_rank as rank
, CASE WHEN substring(lower(player_full_name) from 6 for 5) = 'round' THEN 'Pick' 
	   	WHEN position = 'RDP' THEN 'Pick'
		ELSE position END as _position
, 'sf_value' as _rank_type 
from dynastr.ktc_player_ranks 
UNION ALL
select player_full_name
, team
, case when round(CAST(age AS float)) < 1 then Null else round(CAST(age AS float)) end as age
, one_qb_value as value
, rank as rank
, CASE WHEN substring(lower(player_full_name) from 6 for 5) = 'round' THEN 'Pick' 
	   	WHEN position = 'RDP' THEN 'Pick'
		ELSE position END as _position
, 'one_qb_value' as _rank_type 
from dynastr.ktc_player_ranks )
															   
select player_full_name
,CONCAT(_position, ' ', rank() OVER (partition by _rank_type, _position ORDER BY value DESC)) as pos_rank
, team
, age
, value
, rank
, _position
, _rank_type
from ktc_players