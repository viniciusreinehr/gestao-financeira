"""
Gera um executável único da Gestão Financeira usando PyInstaller — um
programa de verdade, com janela própria (via pywebview), sem depender de
abrir aba de navegador.

Uso normal (uso do dia a dia, sem janela de terminal):
    pip install -r requirements.txt
    pip install -r requirements-build.txt
    python build.py

Uso com janela de terminal visível (útil para depurar problemas na primeira
execução, ex.: erro ao carregar a janela nativa):
    python build.py --console

O executável final fica em dist/GestaoFinanceira(.exe) — pode ser copiado
para qualquer pasta e não precisa mais de Python instalado na máquina.
"""

import os
import shutil
import sys
import time

import PyInstaller.__main__

SEP = ";" if os.name == "nt" else ":"
MODO_CONSOLE = "--console" in sys.argv


def _limpar_pasta(pasta, tentativas=3):
    """Remove build/dist antes de gerar de novo. Se o .exe antigo estiver
    travado (ex.: o programa ainda está rodando em segundo plano, ou o
    antivírus está com ele em uso), avisa claramente em vez de deixar o
    PyInstaller quebrar mais na frente com um erro confuso."""
    for tentativa in range(1, tentativas + 1):
        try:
            shutil.rmtree(pasta)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if tentativa == tentativas:
                print(
                    f"\n❌ Não consegui apagar a pasta '{pasta}' — o arquivo está em uso."
                )
                print(
                    "   Isso geralmente acontece quando o GestaoFinanceira(.exe) ainda"
                )
                print("   está rodando (às vezes escondido em segundo plano).")
                print("\n   O que fazer:")
                print("   1) Abra o Gerenciador de Tarefas (Ctrl+Shift+Esc)")
                print("      e finalize qualquer processo 'GestaoFinanceira'.")
                print(
                    "   2) Feche janelas do Explorer/terminal abertas dentro dessa pasta."
                )
                print("   3) Rode 'python build.py' de novo.")
                sys.exit(1)
            time.sleep(1)


if __name__ == "__main__":
    for pasta in ("build", "dist"):
        _limpar_pasta(pasta)

    args = [
        "run.py",
        "--name=GestaoFinanceira",
        "--onefile",
        "--console" if MODO_CONSOLE else "--windowed",
        f"--add-data=app/templates{SEP}app/templates",
        f"--add-data=app/static{SEP}app/static",
        "--hidden-import=flask_sqlalchemy",
        "--hidden-import=sqlalchemy.dialects.sqlite",
        "--hidden-import=waitress",
        "--collect-all=webview",
        "--noconfirm",
        "--clean",
    ]

    try:
        PyInstaller.__main__.run(args)
    except PermissionError:
        print(
            "\n❌ O PyInstaller não conseguiu escrever o executável (arquivo em uso)."
        )
        print(
            "   Feche o GestaoFinanceira(.exe) — inclusive pelo Gerenciador de Tarefas,"
        )
        print(
            "   caso ele esteja rodando escondido — e rode 'python build.py' de novo."
        )
        sys.exit(1)

    nome_final = "dist/GestaoFinanceira" + (".exe" if os.name == "nt" else "")
    print(f"\nPronto! Executável gerado em: {nome_final}")
    print(
        "Copie esse arquivo para onde quiser — ele cria a pasta 'instance' (banco de dados) ao lado dele."
    )
    if not MODO_CONSOLE:
        print("Ele abre direto em uma janela própria, sem terminal e sem navegador.")
