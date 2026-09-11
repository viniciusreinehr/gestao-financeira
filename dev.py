"""
Modo desenvolvimento: sobe o servidor de debug do Flask, com recarregamento
automático a cada alteração de código e stack trace detalhado no navegador
em caso de erro.

Uso:
    python dev.py

Depois acesse http://127.0.0.1:5000 no navegador manualmente (aqui não abre
janela nativa nem navegador sozinho — isso é só para o dia a dia de rodar
`python run.py` ou o executável final).
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Modo desenvolvimento — recarrega sozinho a cada alteração de código.")
    print("Acesse: http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
