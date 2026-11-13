
-- busca ultima carga
-----------------------------------
select * from gold.fato_carga FC
where sk_data = (select max(sk_data) from gold.fato_carga)
order by 3

