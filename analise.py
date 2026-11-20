"""Importa vendas para SQLite e exibe o faturamento mensal."""

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ESCALA_PRECO = 10_000
COLUNAS = (
    "InvoiceNo", "StockCode", "Description", "Quantity",
    "InvoiceDate", "UnitPrice", "CustomerID", "Country",
)


def ler_linhas(caminho):
    if caminho.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ModuleNotFoundError:
            raise SystemExit("Instale openpyxl com pip install -r requirements.txt.") from None

        planilha = load_workbook(caminho, read_only=True, data_only=True)
        with closing(planilha):
            yield from planilha.active.iter_rows(values_only=True)
    else:
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            yield from csv.reader(arquivo)


def preparar_vendas(linhas):
    cabecalho = tuple(next(linhas, ()))
    if cabecalho != COLUNAS:
        raise ValueError("O arquivo precisa ter as oito colunas da base Online Retail.")

    for linha in linhas:
        fatura, produto, descricao, quantidade, data, preco, cliente, pais = linha
        data_venda = data if isinstance(data, datetime) else datetime.fromisoformat(data)
        preco_unidades = Decimal(str(preco)) * ESCALA_PRECO
        if preco_unidades != int(preco_unidades):
            raise ValueError(f"Preço com mais de quatro casas decimais na fatura {fatura}.")
        yield (
            str(fatura), str(produto), descricao or None, int(quantidade),
            data_venda.isoformat(), int(preco_unidades),
            int(cliente) if cliente else None, pais,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", type=Path, help="Planilha oficial .xlsx ou amostra .csv")
    parser.add_argument("--banco", type=Path, default=PASTA / "varejo.sqlite3")
    args = parser.parse_args()

    if args.arquivo.suffix.lower() not in {".csv", ".xlsx"}:
        parser.error("Use um arquivo .csv ou .xlsx.")

    with closing(sqlite3.connect(args.banco)) as banco, closing(ler_linhas(args.arquivo)) as linhas:
        with banco:
            banco.execute("""
                CREATE TABLE IF NOT EXISTS vendas (
                    fatura TEXT NOT NULL,
                    produto TEXT NOT NULL,
                    descricao TEXT,
                    quantidade INTEGER NOT NULL,
                    data_venda TEXT NOT NULL,
                    preco_unidades INTEGER NOT NULL,
                    cliente INTEGER,
                    pais TEXT NOT NULL
                )
            """)
            banco.execute("DELETE FROM vendas")
            resultado = banco.executemany(
                "INSERT INTO vendas VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                preparar_vendas(linhas),
            )
            total_linhas = resultado.rowcount
            consulta = (PASTA / "consultas.sql").read_text(encoding="utf-8")
            resumo = banco.execute(consulta).fetchall()

    print(f"Banco: {args.banco}")
    print(f"Linhas importadas: {total_linhas}")
    print("Mês       Pedidos   Faturamento")
    for mes, pedidos, unidades in resumo:
        faturamento = Decimal(unidades) / ESCALA_PRECO
        print(f"{mes}   {pedidos:>7}   £{faturamento:,.2f}")


if __name__ == "__main__":
    main()
