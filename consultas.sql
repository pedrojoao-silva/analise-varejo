-- Vendas com quantidade e preço positivos, excluindo cancelamentos.
WITH vendas_validas AS (
    SELECT *
    FROM vendas
    WHERE UPPER(fatura) NOT LIKE 'C%'
      AND quantidade > 0
      AND preco_unidades > 0
)
SELECT SUBSTR(data_venda, 1, 7) AS mes,
       COUNT(DISTINCT fatura) AS pedidos,
       SUM(quantidade * preco_unidades) AS faturamento_unidades
FROM vendas_validas
GROUP BY mes
ORDER BY mes;
