import logging
import os
import sys
import threading
import time
import traceback
import webbrowser

from app import create_app

app = create_app()

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"

# Onde salvar o log de erros: ao lado do executável (modo empacotado) ou
# ao lado deste script (modo desenvolvimento). Assim, se algo falhar numa
# máquina de outra pessoa, basta pedir o conteúdo de "erro.log".
_PASTA_BASE = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.abspath(os.path.dirname(__file__))
)
_LOG_PATH = os.path.join(_PASTA_BASE, "erro.log")

logging.basicConfig(
    filename=_LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

_erro_servidor = {"mensagem": None}


def _mostrar_alerta(titulo, mensagem):
    """Mostra um alerta visível para o usuário mesmo sem console (modo
    --windowed). No Windows usa uma caixa de mensagem nativa; nos demais
    sistemas, imprime no terminal (se houver um)."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 0x10)  # ícone de erro
            return
        except Exception:
            pass
    print(f"{titulo}\n{mensagem}")


def _iniciar_servidor():
    """Sobe o Flask com waitress (servidor de produção) em uma thread separada,
    tanto no modo executável quanto no modo desenvolvimento — a janela nativa
    (ou o navegador, no modo fallback) conversa com esse servidor local."""
    try:
        from waitress import serve

        logging.info("Iniciando servidor em %s", URL)
        serve(app, host=HOST, port=PORT)
    except OSError as erro:
        # Caso mais comum: porta 5000 já em uso (outra instância já rodando,
        # ou outro programa usando a mesma porta).
        msg = f"Não foi possível iniciar o servidor na porta {PORT}: {erro}"
        logging.error(msg)
        _erro_servidor["mensagem"] = msg
    except Exception:
        logging.error(
            "Erro inesperado ao iniciar o servidor:\n%s", traceback.format_exc()
        )
        _erro_servidor["mensagem"] = (
            "Erro inesperado ao iniciar o servidor. Veja erro.log para detalhes."
        )


def _aguardar_servidor(tentativas=40):
    """Espera o servidor responder antes de abrir a janela, para evitar a
    tela branca de 'conexão recusada' no primeiro instante."""
    import urllib.request

    for _ in range(tentativas):
        if _erro_servidor["mensagem"]:
            return False
        try:
            urllib.request.urlopen(URL, timeout=0.5)
            return True
        except Exception:
            time.sleep(0.15)
    return False


def _rodar_modo_fallback():
    """Sem pywebview disponível (ou sem suporte gráfico no sistema): abre no
    navegador padrão e mantém o processo vivo até o usuário encerrar."""
    webbrowser.open(URL)
    print(f"Gestão Financeira rodando em {URL}")
    print("Deixe esta janela aberta enquanto estiver usando o sistema.")
    print("Feche esta janela (ou Ctrl+C) para encerrar.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    threading.Thread(target=_iniciar_servidor, daemon=True).start()
    ok = _aguardar_servidor()

    if not ok:
        mensagem = _erro_servidor["mensagem"] or (
            f"O servidor não respondeu em {URL} depois de alguns segundos.\n"
            f"Verifique o arquivo erro.log nesta mesma pasta para mais detalhes."
        )
        logging.error("Falha ao iniciar: %s", mensagem)
        _mostrar_alerta("Gestão Financeira — não foi possível iniciar", mensagem)
        return

    try:
        import webview
    except ImportError:
        logging.warning("pywebview não instalado/empacotado; usando modo navegador.")
        _rodar_modo_fallback()
        return

    try:
        webview.create_window(
            "Gestão Financeira",
            URL,
            width=1320,
            height=860,
            min_size=(960, 620),
        )
        # webview.start() bloqueia até a janela ser fechada; como o servidor
        # roda em thread daemon, o processo inteiro encerra junto.
        webview.start()
    except Exception:
        # Ambiente sem suporte a janela nativa — no Windows, o motivo mais
        # comum é o WebView2 Runtime não estar instalado. Registra o erro
        # completo no log e cai para o modo navegador.
        logging.error("Falha ao abrir a janela nativa:\n%s", traceback.format_exc())
        print("Não foi possível abrir a janela nativa. Abrindo no navegador...")
        _rodar_modo_fallback()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.error("Erro fatal não tratado:\n%s", traceback.format_exc())
        _mostrar_alerta(
            "Gestão Financeira — erro inesperado",
            f"Ocorreu um erro inesperado. Veja o arquivo erro.log nesta pasta:\n{_LOG_PATH}",
        )
