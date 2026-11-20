import csv
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1]
AMOSTRA = PASTA / "dados" / "amostra.csv"


class FluxoVarejoTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.banco = self.pasta / "vendas.sqlite3"

    def rodar(self, script, *args):
        return subprocess.run(
            [sys.executable, str(PASTA / script), "--banco", str(self.banco), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8",
        )

    def criar_csv(self, linhas):
        arquivo = self.pasta / "entrada.csv"
        with arquivo.open("w", encoding="utf-8", newline="") as saida:
            csv.writer(saida).writerows(linhas)
        return arquivo

    def ler_amostra(self):
        with AMOSTRA.open(encoding="utf-8", newline="") as arquivo:
            return list(csv.reader(arquivo))

    def test_importacao_invalida_preserva_banco(self):
        resultado = self.rodar("analise.py", AMOSTRA)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        cabecalho, primeira, segunda, *_ = self.ler_amostra()
        segunda[3] = "1.5"
        for linhas, mensagem in (
            ([cabecalho], "não contém linhas de vendas"),
            ([cabecalho, primeira, segunda], "Linha 3, campo Quantity"),
        ):
            with self.subTest(mensagem=mensagem):
                resultado = self.rodar("analise.py", self.criar_csv(linhas))
                self.assertEqual(resultado.returncode, 2)
                self.assertIn(mensagem, resultado.stderr)
                with closing(sqlite3.connect(self.banco)) as banco:
                    self.assertEqual(banco.execute("SELECT COUNT(*) FROM vendas").fetchone(), (5,))

    def test_resumo_rankings_e_agendamento(self):
        linhas = self.ler_amostra()
        linhas.extend([
            ["C100005", "X", "Cancelada", 8, "2011-01-10", 100, 100, "France"],
            ["100006", "X", "Quantidade negativa", -8, "2011-01-10", 100, 100, "France"],
            ["100007", "X", "Preço negativo", 8, "2011-01-10", -100, 100, "France"],
            ["100001", "A2", "Caderno", 1, "2011-01-10", 3, 100, "United Kingdom"],
        ])
        resultado = self.rodar("analise.py", self.criar_csv(linhas))
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertRegex(resultado.stdout, r"2011-01\s+1\s+£16\.50")
        destino = self.pasta / "relatorios"
        resultado = self.rodar("relatorio.py", "--data", "2011-02-11", "--saida", destino)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertFalse(destino.exists())

        for opcao in (("--mes", "2011-01"), ("--data", "2011-02-10")):
            resultado = self.rodar("relatorio.py", *opcao, "--saida", destino)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            texto = (destino / "email-2011-01.txt").read_text(encoding="utf-8")
            self.assertIn("Faturamento bruto: £16,50\nPedidos: 1\nTicket médio: £16,50", texto)
            self.assertIn("Maior: Caneca (A1), Caderno (A2) (2 unidades)", texto)
            self.assertIn("Variação mensal: indisponível por cobertura parcial ou ausente", texto)
            self.assertNotIn("France", texto)

        resultado = self.rodar("relatorio.py", "--mes", "2011-02", "--saida", destino)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("Faturamento bruto: £12,00", resultado.stdout)
        self.assertNotIn("Amostra", resultado.stdout)

    def test_comparacao_com_mes_anterior(self):
        cabecalho = self.ler_amostra()[0]
        arquivo = self.criar_csv([
            cabecalho,
            ["1", "A1", "Caneca", 2, "2011-01-01", 5, 100, "France"],
            ["2", "A1", "Caneca", 3, "2011-02-28", 5, 100, "France"],
        ])
        resultado = self.rodar("analise.py", arquivo)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        resultado = self.rodar("relatorio.py", "--mes", "2011-02", "--saida", self.pasta)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("Variação do faturamento frente a 2011-01: +50,0%", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
