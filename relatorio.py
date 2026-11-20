"""Gera o relatório do mês anterior e um rascunho de e-mail no dia 10."""

import argparse
import re
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from analise import ESCALA_PRECO, preparar_consultas

PASTA = Path(__file__).resolve().parent
CONSULTA = """
WITH vendas_do_mes AS (
    SELECT * FROM vendas_validas
    WHERE data_venda >= ? AND data_venda < ?
), ranking_produtos AS (
    SELECT produto AS nome, SUM(quantidade) AS valor,
           MIN(NULLIF(TRIM(descricao), '')) AS descricao
    FROM vendas_do_mes
    GROUP BY produto
), ranking_paises AS (
    SELECT pais AS nome, SUM(quantidade * preco_unidades) AS valor
    FROM vendas_do_mes
    GROUP BY pais
)
SELECT 'produto', nome, valor, descricao FROM ranking_produtos
UNION ALL
SELECT 'país', nome, valor, NULL FROM ranking_paises
ORDER BY valor DESC, nome;
"""


def extremos(itens, formatar):
    maior = itens[0][1]
    menor = itens[-1][1]
    resumo = []
    for rotulo, limite in (("Maior", maior), ("Menor", menor)):
        empatados = [nome for nome, valor in itens if valor == limite]
        nomes = ", ".join(empatados[:5])
        if len(empatados) > 5:
            nomes += f" e mais {len(empatados) - 5} em empate"
        resumo.append(f"{rotulo}: {nomes} ({formatar(limite)})")
    return resumo


def formatar_libras(unidades):
    valor = Decimal(unidades) / ESCALA_PRECO
    return "£" + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_unidades(valor):
    return "1 unidade" if valor == 1 else f"{valor} unidades"


def ler_mes(valor):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", valor):
        raise argparse.ArgumentTypeError("Use o formato AAAA-MM.")
    try:
        mes = date.fromisoformat(valor + "-01")
        if not date(1, 2, 1) <= mes < date(9999, 12, 1):
            raise ValueError
        return mes
    except ValueError:
        raise argparse.ArgumentTypeError("Informe um mês válido com mês anterior e seguinte.") from None


def proximo_mes(mes):
    return (mes.replace(day=28) + timedelta(days=4)).replace(day=1)


def resumo_mensal(banco, inicio, fim):
    return banco.execute("""
        SELECT COUNT(DISTINCT fatura), COALESCE(SUM(quantidade * preco_unidades), 0)
        FROM vendas_validas WHERE data_venda >= ? AND data_venda < ?
    """, (inicio.isoformat(), fim.isoformat())).fetchone()


def periodo_coberto(inicio, fim, primeira, ultima):
    return bool(primeira and primeira[:10] <= inicio.isoformat()
                and ultima[:10] >= (fim - timedelta(days=1)).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    periodo = parser.add_mutually_exclusive_group()
    periodo.add_argument("--mes", type=ler_mes, help="Gera o relatório do mês AAAA-MM sob demanda")
    periodo.add_argument("--data", type=date.fromisoformat, default=date.today(),
                        help="Simula uma data de execução no formato AAAA-MM-DD")
    parser.add_argument("--banco", type=Path, default=PASTA / "varejo.sqlite3")
    parser.add_argument("--saida", type=Path, default=PASTA / "relatorios")
    args = parser.parse_args()

    if args.mes is None and args.data.day != 10:
        print("O relatório é gerado quando o script roda no dia 10.")
        return

    if args.mes:
        inicio = args.mes
        fim = proximo_mes(inicio)
    else:
        fim = args.data.replace(day=1)
        if fim < date(1, 3, 1):
            parser.error("A data precisa permitir consultar os dois meses anteriores.")
        inicio = (fim - timedelta(days=1)).replace(day=1)
    anterior = (inicio - timedelta(days=1)).replace(day=1)
    mes = inicio.strftime("%Y-%m")

    if not args.banco.is_file():
        parser.error("Importe a planilha para criar o banco antes de gerar o relatório.")

    with closing(sqlite3.connect(args.banco.resolve().as_uri() + "?mode=ro", uri=True)) as banco:
        preparar_consultas(banco)
        banco.execute("BEGIN")
        pedidos, faturamento = resumo_mensal(banco, inicio, fim)
        _, faturamento_anterior = resumo_mensal(banco, anterior, inicio)
        linhas = banco.execute(CONSULTA, (inicio.isoformat(), fim.isoformat())).fetchall()
        primeira, ultima = banco.execute("SELECT MIN(data_venda), MAX(data_venda) FROM vendas").fetchone()

    mensagem = [f"Assunto: Resultado de vendas de {mes}", "", "Olá, Diretoria,", ""]
    ticket = formatar_libras(Decimal(faturamento) / pedidos) if pedidos else "indisponível"
    mensagem.extend([
        f"Faturamento bruto: {formatar_libras(faturamento)}",
        f"Pedidos: {pedidos}",
        f"Ticket médio: {ticket}",
    ])
    if not (periodo_coberto(inicio, fim, primeira, ultima)
            and periodo_coberto(anterior, inicio, primeira, ultima)):
        mensagem.append("Variação mensal: indisponível por cobertura parcial ou ausente.")
    elif not faturamento_anterior:
        mensagem.append("Variação mensal: indisponível porque o mês anterior teve faturamento zero.")
    else:
        variacao = (Decimal(faturamento) / faturamento_anterior - 1) * 100
        percentual = f"{variacao:+.1f}".replace(".", ",")
        mensagem.append(f"Variação do faturamento frente a {anterior:%Y-%m}: {percentual}%")

    if primeira and not periodo_coberto(inicio, fim, primeira, ultima):
        mensagem.append(f"Cobertura da base: {primeira[:10]} a {ultima[:10]}.")

    if linhas:
        produtos = [
            (f"{descricao} ({nome})" if descricao else nome, valor)
            for tipo, nome, valor, descricao in linhas if tipo == "produto"
        ]
        paises = [(nome, valor) for tipo, nome, valor, _ in linhas if tipo == "país"]
        for titulo, ranking, formatar in (
            ("Produtos por unidades vendidas", produtos, formatar_unidades),
            ("Países por faturamento bruto", paises, formatar_libras),
        ):
            mensagem.extend(["", titulo, *extremos(ranking, formatar), "Top 5"])
            mensagem.extend(
                f"{posicao}. {nome}: {formatar(valor)}"
                for posicao, (nome, valor) in enumerate(ranking[:5], start=1)
            )
    else:
        mensagem.extend(["", "A base importada não contém vendas válidas para este mês."])

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
