import sqlite3
from sqlite3 import Error

# Função para criar conexão com o banco de dados SQLite
def create_connection(db_file):
    """ cria uma conexão com o banco de dados SQLite """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn

# Função para consultar todos os trades no banco de dados
def select_all_trades(conn):
    """ consulta todos os trades no banco de dados """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades")

        rows = cursor.fetchall()

        for row in rows:
            print(row)
    except Error as e:
        print(e)

if __name__ == '__main__':
    database = "trades.db"

    # cria uma conexão com o banco de dados
    conn = create_connection(database)
    with conn:
        print("Consultando todos os trades armazenados no banco de dados:")
        select_all_trades(conn)
