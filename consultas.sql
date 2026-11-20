-- Execute vendas_validas.sql na mesma conexão antes desta consulta.
SELECT SUBSTR(data_venda, 1, 7) AS mes,
       COUNT(DISTINCT fatura) AS pedidos,
       SUM(quantidade * preco_unidades) AS faturamento_unidades
FROM vendas_validas
GROUP BY mes
ORDER BY mes;
