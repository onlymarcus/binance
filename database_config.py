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

# Função para criar a tabela de trades
def create_table(conn):
    """ cria a tabela de trades no banco de dados """
    try:
        sql_create_trades_table = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            time TEXT NOT NULL,
            price REAL NOT NULL,
            qty REAL NOT NULL,
            is_buyer_maker BOOLEAN NOT NULL
        );"""
        cursor = conn.cursor()
        cursor.execute(sql_create_trades_table)
    except Error as e:
        print(e)

# Função para inserir um trade no banco de dados
def insert_trade(conn, trade):
    """ insere um novo trade no banco de dados """
    sql = ''' INSERT INTO trades(time, price, qty, is_buyer_maker)
              VALUES(?,?,?,?) '''
    cursor = conn.cursor()
    cursor.execute(sql, trade)
    conn.commit()
    return cursor.lastrowid

# Função para buscar trades dos últimos 15 minutos
def fetch_recent_trades(conn, minutes=15):
    """ busca os trades dos últimos X minutos """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM trades
        WHERE time >= datetime('now', '-{} minutes')
        ORDER BY time
    """.format(minutes))
    rows = cursor.fetchall()
    return rows
