"""Gera o relatório do mês anterior e um rascunho de e-mail no dia 10."""

import argparse
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
CONSULTA = """
WITH vendas_validas AS (
    SELECT * FROM vendas
    WHERE data_venda >= ? AND data_venda < ?
      AND UPPER(fatura) NOT LIKE 'C%'
      AND quantidade > 0 AND preco_unidades > 0
), ranking_produtos AS (
    SELECT produto AS nome, SUM(quantidade) AS valor
    FROM vendas_validas
    GROUP BY produto
), ranking_paises AS (
    SELECT pais AS nome, SUM(quantidade * preco_unidades) AS valor
    FROM vendas_validas
    GROUP BY pais
)
SELECT 'produto', nome, valor FROM ranking_produtos
UNION ALL
SELECT 'país', nome, valor FROM ranking_paises
ORDER BY valor, nome;
"""


def extremos(itens, formatar):
    menor = itens[0][1]
    maior = itens[-1][1]
    return [
        f"{rotulo}: {', '.join(nome for nome, valor in itens if valor == limite)}"
        f" ({formatar(limite)})"
        for rotulo, limite in (("Maior", maior), ("Menor", menor))
    ]


def formatar_libras(unidades):
    inteiro, fracao = divmod(unidades, 10_000)
    reais = f"{inteiro:,}".replace(",", ".")
    return f"£{reais},{fracao:04d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=date.fromisoformat, default=date.today(),
                        help="Simula uma data de execução no formato AAAA-MM-DD")
    parser.add_argument("--banco", type=Path, default=PASTA / "varejo.sqlite3")
    parser.add_argument("--saida", type=Path, default=PASTA / "relatorios")
    args = parser.parse_args()

    if args.data.day != 10:
        print("O relatório é gerado quando o script roda no dia 10.")
        return

    fim = args.data.replace(day=1)
    inicio = (fim - timedelta(days=1)).replace(day=1)
    mes = inicio.strftime("%Y-%m")

    if not args.banco.is_file():
        parser.error("Importe a planilha para criar o banco antes de gerar o relatório.")

    with closing(sqlite3.connect(args.banco.resolve().as_uri() + "?mode=ro", uri=True)) as banco:
        linhas = banco.execute(CONSULTA, (inicio.isoformat(), fim.isoformat())).fetchall()
        primeira, ultima = banco.execute("SELECT MIN(data_venda), MAX(data_venda) FROM vendas").fetchone()

    mensagem = [f"Assunto: Resultado de vendas de {mes}", "", "Olá, Diretoria,", ""]
    if linhas:
        produtos = [(nome, valor) for tipo, nome, valor in linhas if tipo == "produto"]
        paises = [(nome, valor) for tipo, nome, valor in linhas if tipo == "país"]
        mensagem.extend([
            "Produtos por unidades vendidas",
            *extremos(produtos, lambda valor: f"{valor} unidades"),
            "",
            "Países por faturamento bruto",
            *extremos(paises, formatar_libras),
        ])
        if primeira[:10] > inicio.isoformat() or ultima[:10] < (fim - timedelta(days=1)).isoformat():
            mensagem.extend(["", "O período contém dados parciais na base importada."])
    else:
        mensagem.append("A base importada não contém vendas válidas para este mês.")

    mensagem.extend([
        "",
        "A base de origem não informa vendedor ou estado.",
        "",
        "Atenciosamente,",
        "Equipe de Análise de Dados",
    ])
    texto = "\n".join(mensagem) + "\n"
    args.saida.mkdir(parents=True, exist_ok=True)
    destino = args.saida / f"email-{mes}.txt"
    destino.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Rascunho salvo em {destino}")


if __name__ == "__main__":
    main()
