"""Importa vendas para SQLite e exibe o faturamento mensal."""

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal, DecimalException
from itertools import chain
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

    for numero, linha in enumerate(linhas, start=2):
        if len(linha) != len(COLUNAS):
            raise ValueError(f"Linha {numero}: esperadas oito colunas.")

        fatura, produto, descricao, quantidade, data, preco, cliente, pais = linha
        valores = []
        for campo, valor, converter in (
            ("InvoiceNo", fatura, texto_obrigatorio),
            ("StockCode", produto, texto_obrigatorio),
            ("Description", descricao, lambda valor: valor or None),
            ("Quantity", quantidade, inteiro),
            ("InvoiceDate", data, lambda valor: (
                valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)
            ).isoformat()),
            ("UnitPrice", preco, lambda valor: inteiro(Decimal(str(valor)) * ESCALA_PRECO)),
            ("CustomerID", cliente, lambda valor: inteiro(valor) if valor not in (None, "") else None),
            ("Country", pais, texto_obrigatorio),
        ):
            try:
                valores.append(converter(valor))
            except (ValueError, TypeError, DecimalException, OverflowError) as erro:
                raise ValueError(f"Linha {numero}, campo {campo}: {erro}") from erro
        yield tuple(valores)


def texto_obrigatorio(valor):
    if valor is None or not str(valor).strip():
        raise ValueError("valor obrigatório")
    return str(valor).strip()


def inteiro(valor):
    numero = Decimal(str(valor))
    if not numero.is_finite() or numero != numero.to_integral_value():
        raise ValueError("valor fora da precisão esperada")
    if not -(2**63) <= numero < 2**63:
        raise ValueError("valor fora do intervalo do SQLite")
    return int(numero)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", type=Path, help="Planilha oficial .xlsx ou amostra .csv")
    parser.add_argument("--banco", type=Path, default=PASTA / "varejo.sqlite3")
    args = parser.parse_args()

    if args.arquivo.suffix.lower() not in {".csv", ".xlsx"}:
        parser.error("Use um arquivo .csv ou .xlsx.")

    try:
        importar(args.arquivo, args.banco)
    except (ValueError, OSError, sqlite3.Error) as erro:
        parser.error(str(erro))


def importar(arquivo, caminho_banco):
    with closing(ler_linhas(arquivo)) as linhas:
        vendas = preparar_vendas(linhas)
        primeira = next(vendas, None)
        if primeira is None:
            raise ValueError("O arquivo não contém linhas de vendas.")
        with closing(sqlite3.connect(caminho_banco)) as banco:
            total_linhas, resumo = salvar_vendas(banco, chain((primeira,), vendas))

    print(f"Banco: {caminho_banco}")
    print(f"Linhas importadas: {total_linhas}")
    print("Mês       Pedidos   Faturamento")
    for mes, pedidos, unidades in resumo:
        faturamento = Decimal(unidades) / ESCALA_PRECO
        print(f"{mes}   {pedidos:>7}   £{faturamento:,.2f}")


def salvar_vendas(banco, vendas):
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
            vendas,
        )
        total_linhas = resultado.rowcount
        consulta = (PASTA / "consultas.sql").read_text(encoding="utf-8")
        preparar_consultas(banco)
        resumo = banco.execute(consulta).fetchall()
    return total_linhas, resumo


def preparar_consultas(banco):
    banco.execute((PASTA / "vendas_validas.sql").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
