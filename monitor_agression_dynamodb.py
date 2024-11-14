import ccxt.async_support as ccxt
import pandas as pd
import time
import hmac
import hashlib
import requests
import telebot
from os import getenv
import dotenv
import logging
import asyncio
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

# Configurações de logging
logging.basicConfig(level=logging.INFO)

# Acessando a API do Telegram usando a chave da API
dotenv.load_dotenv()
CHAVE_API = getenv("CHAVE_API")
CHANNEL_ID = getenv("CHANNEL_ID")
TELEGRAM_BOT = telebot.TeleBot(CHAVE_API, parse_mode=None)

# Configurações da API da Binance
BINANCE_API_KEY = getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = getenv("BINANCE_SECRET_KEY")
BASE_URL = "https://api.binance.com"

# Configurações da AWS DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
DYNAMODB_TABLE_NAME = "TradesTable"

# Função para enviar mensagem para o Telegram
def send_telegram_message(message):
    try:
        TELEGRAM_BOT.send_message(CHANNEL_ID, message)
        logging.info(f"Mensagem enviada: {message}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem: {e}")

# Função para assinar a requisição
def sign_request(query_string):
    return hmac.new(BINANCE_SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# Função para obter dados de trades históricos da Binance
def get_historical_trades(symbol, limit=1000, from_id=None):
    endpoint = f"{BASE_URL}/api/v3/historicalTrades"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    params = {"symbol": symbol, "limit": limit}
    if from_id:
        params["fromId"] = from_id
    response = requests.get(endpoint, headers=headers, params=params)
    return response.json()

# Função para salvar trades no DynamoDB
def save_trades_to_dynamodb(trades):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    with table.batch_writer() as batch:
        for trade in trades:
            try:
                batch.put_item(
                    Item={
                        'trade_id': str(trade['id']),
                        'symbol': trade['symbol'],
                        'price': str(trade['price']),
                        'qty': str(trade['qty']),
                        'time': str(trade['time']),
                        'isBuyerMaker': trade['isBuyerMaker']
                    }
                )
            except (ClientError, NoCredentialsError) as e:
                logging.error(f"Erro ao salvar o trade {trade['id']} no DynamoDB: {e}")

# Função para calcular volume de agressão com base nos takers
def calculate_aggression(symbol, interval_minutes=1, lookback_minutes=15):
    logging.info(f"Calculando agressão para {symbol}")
    interval_seconds = interval_minutes * 60
    end_time = int(time.time())
    start_time = end_time - (lookback_minutes * 60)

    trades = []
    from_id = None

    while True:
        # Obter os trades
        batch_trades = get_historical_trades(symbol, from_id=from_id)
        if not batch_trades:
            break
        trades.extend(batch_trades)

        # Atualizar o from_id para o próximo lote
        from_id = batch_trades[-1]['id'] + 1

        # Checar tempo do último trade
        last_trade_time = batch_trades[-1]['time'] / 1000
        if last_trade_time < start_time:
            break

        # Logging para verificar progresso da coleta de dados
        logging.info(f"Coletados {len(trades)} trades até agora...")

        # Esperar um pouco para evitar limitação de taxa da API
        time.sleep(0.5)

    # Salvar trades coletados no DynamoDB
    save_trades_to_dynamodb(trades)

    # Filtrando apenas os trades que estão dentro do período desejado
    df = pd.DataFrame(trades)
    if df.empty:
        logging.warning("Nenhum trade foi coletado. Aguardando mais dados...")
        return

    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df = df[df['time'] >= pd.to_datetime(start_time, unit='s')]
    df['price'] = df['price'].astype(float)
    df['qty'] = df['qty'].astype(float)

    # Verificando se há trades suficientes após o filtro
    if df.empty:
        logging.warning("Nenhum trade relevante no período desejado. Aguardando mais dados...")
        return

    # Calculando volumes de agressão compradora e vendedora
    df['buy_aggression'] = df.apply(lambda row: row['qty'] if row['isBuyerMaker'] == False else 0, axis=1)
    df['sell_aggression'] = df.apply(lambda row: row['qty'] if row['isBuyerMaker'] == True else 0, axis=1)

    # Resampling para intervalos de 1 minuto
    df_resampled = df.set_index('time').resample(f'{interval_minutes}min').agg({
        'buy_aggression': 'sum',
        'sell_aggression': 'sum'
    }).fillna(0)  # Preenchendo valores nulos com zero

    # Logging das somas de agressão para cada intervalo
    for index, row in df_resampled.iterrows():
        logging.info(f"Intervalo {index}: Agressão Compradora: {row['buy_aggression']:.2f} BTC, Agressão Vendedora: {row['sell_aggression']:.2f} BTC")

    # Calcular saldo de agressão e limites
    df_resampled['aggression_balance'] = df_resampled['buy_aggression'] - df_resampled['sell_aggression']
    
    # Verificando se há dados suficientes para o cálculo
    if df_resampled['aggression_balance'].count() < 15:
        logging.warning("Aguardando completar 15 minutos de dados para calcular os limites de agressão.")
        return

    aggression_mean = df_resampled['aggression_balance'].mean()
    aggression_std = df_resampled['aggression_balance'].std()
    upper_limit = aggression_mean + aggression_std
    lower_limit = aggression_mean - aggression_std

    logging.info(f"Saldo Médio da Agressão: {aggression_mean:.2f} BTC")
    logging.info(f"Limite Superior (Compra): {upper_limit:.2f} BTC")
    logging.info(f"Limite Inferior (Venda): {lower_limit:.2f} BTC")

    # Verificar e enviar sinais
    last_aggression = df_resampled['aggression_balance'].iloc[-1]
    last_price = df['price'].iloc[-1]

    if last_aggression > upper_limit:
        message = (
            f"Sinal de Compra: BTC/USDT\n"
            f"Saldo da agressão compradora: {last_aggression:.2f} BTC\n"
            f"Preço atual: {last_price:.2f} USDT\n"
        )
        send_telegram_message(message)

    elif last_aggression < lower_limit:
        message = (
            f"Sinal de Venda: BTC/USDT\n"
            f"Saldo da agressão vendedora: {last_aggression:.2f} BTC\n"
            f"Preço atual: {last_price:.2f} USDT\n"
        )
        send_telegram_message(message)

# Função principal de execução
def monitor_aggression():
    symbol = 'BTCUSDT'
    while True:
        calculate_aggression(symbol)
        time.sleep(60)  # Espera de 1 minuto entre verificações

if __name__ == "__main__":
    logging.info("Iniciando o monitoramento de agressão")
    monitor_aggression()

# A IDEIA É FAZER UM SCRIPT SEPARADO PARA COLETAR OS DADOS E SALVAR NO DYNAMODB, E UM SCRIPT AQUI PRA FAZER AS ANÁLISES
