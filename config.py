import os
import sys

if getattr(sys, "frozen", False):
    # Rodando como executável (PyInstaller): guarda o banco de dados ao lado
    # do executável, não dentro da pasta temporária de extração (_MEIPASS),
    # que é apagada a cada execução.
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "gestao-financeira-familia-dev")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "financeiro.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    # Quantos meses para frente o sistema deve manter lançamentos
    # recorrentes/provisionados gerados automaticamente. O dashboard mostra
    # o mês atual + esse número de meses seguintes (5 = 6 meses no total).
    HORIZONTE_MESES = 5
    # Quantos meses de histórico usar para calcular a média de
    # provisionamento das contas variáveis (luz, água, internet, etc.)
    MESES_MEDIA_PROVISIONAMENTO = 3
