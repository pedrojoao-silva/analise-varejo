# Análise de varejo com Python e SQLite

O projeto importa vendas para um banco SQLite local. Uma consulta SQL calcula o número de pedidos e o faturamento bruto de vendas por mês, em libras esterlinas.

## Rodar com dados fictícios

```bash
python3 analise.py dados/amostra.csv
```

O script cria o arquivo `varejo.sqlite3`. A amostra tem cinco linhas e gera £13.50 em janeiro e £12.00 em fevereiro. O banco guarda todas as linhas. A consulta exclui cancelamentos, quantidades não positivas e preços não positivos para calcular o faturamento bruto. Cada importação substitui os dados da tabela `vendas` por inteiro em uma transação.

## Importar as vendas reais

Baixe a base [Online Retail da UCI](https://archive.ics.uci.edu/dataset/352/online+retail), extraia a planilha e salve `Online Retail.xlsx` na pasta `dados`. Depois execute os comandos abaixo em um ambiente Python com `pip`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analise.py "dados/Online Retail.xlsx"
```

A base tem 541.909 linhas de itens de pedidos de uma loja virtual do Reino Unido, de dezembro de 2010 a dezembro de 2011. Dezembro de 2011 é parcial. Os preços são armazenados como números inteiros em unidades de £0,0001 para preservar a precisão no SQL.

Fonte dos dados reais: Daqing Chen, *Online Retail* (2015), UCI Machine Learning Repository, [DOI 10.24432/C5BW33](https://doi.org/10.24432/C5BW33), licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
