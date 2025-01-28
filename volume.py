import ccxt.async_support as ccxt
import pandas as pd
import time
import telebot
from os import getenv
import dotenv
import logging
import asyncio

# Configurações de logging
logging.basicConfig(level=logging.INFO)

# Acessando a API do Telegram usando a chave da API
dotenv.load_dotenv()
CHAVE_API = getenv("CHAVE_API")
CHANNEL_ID = getenv("CHANNEL_ID")
CHANNEL_IDB = getenv("CHANNEL_IDB")
bot = telebot.TeleBot(CHAVE_API, parse_mode=None)

# Função para enviar mensagem para o Telegram de forma assíncrona
# Função para enviar mensagem para o Telegram de forma assíncrona
async def send_telegram_message(message, chat_ids=[CHANNEL_ID, CHANNEL_IDB]):
    try:
        for chat_id in chat_ids:
            bot.send_message(chat_id, message)
            logging.info(f"Mensagem enviada para o chat {chat_id}: {message}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem: {e}")


# Função para obter dados da Binance de forma assíncrona
async def get_binance_data(binance, symbol, timeframe, limit):
    logging.info(f"Obtendo dados de {symbol} para o timeframe {timeframe}")
    ohlcv = await binance.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['buy_volume'] = df.apply(lambda row: row['volume'] * row['close'] if row['close'] > row['open'] else 0, axis=1)
    df['sell_volume'] = df.apply(lambda row: row['volume'] * row['close'] if row['close'] <= row['open'] else 0, axis=1)
    return df

# Função para filtrar símbolos por volume diário
async def filter_symbols_by_daily_volume(binance, min_volume):
    logging.info(f"Filtrando símbolos com volume diário maior que {min_volume}")
    tickers = await binance.fetch_tickers()
    symbols = [symbol for symbol, ticker in tickers.items() if ticker['quoteVolume'] > min_volume and symbol.endswith('/USDT')]
    logging.info(f"Símbolos filtrados: {symbols}")
    return symbols

# Função principal para monitorar o volume
async def monitor_volume():
    min_daily_volume = 100_000_000  # Volume diário mínimo de 100 milhões de USDT
    timeframe_15m = '15m'
    timeframe_1m = '1m'
    limit = 3  # Limite para obter dados das últimas velas

    binance = ccxt.binance()

    while True:
        logging.info("Iniciando nova rodada de monitoramento de volume")
        symbols = await filter_symbols_by_daily_volume(binance, min_daily_volume)

        tasks = []
        results = []
        for symbol in symbols:
            tasks.append(process_symbol(binance, symbol, timeframe_15m, timeframe_1m, limit, results))

        # Executa todas as tarefas de forma assíncrona
        await asyncio.gather(*tasks)

        # Enviar uma única mensagem com os resultados
        if results:
            message = "Search result:\n"
            for result in results:
                message += result + "\n"
            await send_telegram_message(message)
        else:
            logging.info("no recommendations at the last minute.")

        # Aguardar 5 minutos antes da próxima verificação
        logging.info("Aguardando 1 minutos para a próxima rodada de verificação")
        await asyncio.sleep(60)

# Função para processar cada símbolo e verificar volume
async def process_symbol(binance, symbol, timeframe_15m, timeframe_1m, limit, results):
    try:
        # Obter dados dos últimos 15 minutos
        logging.info(f"Obtendo volume dos últimos 15 minutos para {symbol}")
        df_15m = await get_binance_data(binance, symbol, timeframe_15m, limit)
        buy_volume_15m = df_15m['buy_volume'].sum()
        sell_volume_15m = df_15m['sell_volume'].sum()
        volume_balance_15m = buy_volume_15m - sell_volume_15m

        # Obter dados do último minuto
        logging.info(f"Obtendo volume do último minuto para {symbol}")
        df_1m = await get_binance_data(binance, symbol, timeframe_1m, limit)
        buy_volume_1m = df_1m['buy_volume'].sum()
        sell_volume_1m = df_1m['sell_volume'].sum()
        volume_balance_1m = buy_volume_1m - sell_volume_1m

        # Verificar se o módulo do saldo do último minuto é superior a 80% do módulo do saldo dos últimos 15 minutos
        if abs(volume_balance_1m) > 0.8 * abs(volume_balance_15m):
            if volume_balance_1m > 0:
                alert_message = "Alert! High volume purchase (Compra forte)"
            else:
                alert_message = "Alert! High volume sales(Venda forte)"
            quantidade = abs(volume_balance_1m / df_1m['close'].iloc[-1])
            valor = abs(volume_balance_1m)
            preco_medio = valor / quantidade

            logging.info(f"{alert_message} para {symbol}")
            result_message = (
                f"{alert_message}: {symbol}\n"
                f"Quantity: {quantidade:,.2f} {symbol.split('/')[0]}\n"
                f"Value: {valor:,.2f} USDT\n"
                f"Average Price: {preco_medio:,.8f} USDT\n"
            )
            results.append(result_message)
        else:
            logging.info(f"Saldo do último minuto para {symbol} não excedeu 80% do saldo dos últimos 15 minutos")
    except Exception as e:
        logging.error(f"Erro ao processar {symbol}: {e}")

if __name__ == "__main__":
    # Iniciar o monitoramento de volume de forma assíncrona
    logging.info("Iniciando o monitoramento de volume")
    asyncio.run(monitor_volume())
