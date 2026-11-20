-- Regra compartilhada de faturamento bruto.
CREATE TEMP VIEW IF NOT EXISTS vendas_validas AS
SELECT *
FROM main.vendas
WHERE UPPER(fatura) NOT LIKE 'C%'
  AND quantidade > 0
  AND preco_unidades > 0;
