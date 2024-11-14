import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import time
import telebot
import logging
from os import getenv
import dotenv
from datetime import datetime, timedelta

# Configurações de logging
logging.basicConfig(level=logging.INFO)

# Acessando a API do Telegram usando a chave da API
dotenv.load_dotenv()
CHAVE_API = getenv("CHAVE_API")
CHANNEL_ID = getenv("CHANNEL_ID")
bot = telebot.TeleBot(CHAVE_API, parse_mode=None)

# Função para enviar mensagem para o Telegram de forma assíncrona
async def send_telegram_message(message, chat_id=CHANNEL_ID):
    try:
        bot.send_message(chat_id, message)
        logging.info(f"Mensagem enviada: {message}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem: {e}")

# Função para obter dados da Binance de forma assíncrona
async def get_binance_data(binance, symbol):
    ticker = await binance.fetch_ticker(symbol)
    return ticker

# Função para filtrar símbolos por volume diário
async def filter_symbols_by_daily_volume(binance, min_volume):
    logging.info(f"Filtrando símbolos com volume diário maior que {min_volume}")
    tickers = await binance.fetch_tickers()
    stablecoins = ["USDT", "BUSD", "USDC", "FDUSD", "TUSD", "DAI"]
    symbols = [
        symbol for symbol, ticker in tickers.items()
        if ticker['quoteVolume'] > min_volume 
        and symbol.endswith('/USDT')
        and not any(stablecoin + '/USDT' == symbol for stablecoin in stablecoins)
    ]
    logging.info(f"Símbolos filtrados: {symbols}")
    return symbols

# Função principal para monitorar o ATH
async def monitor_ath():
    min_daily_volume = 4_000_000  # Volume diário mínimo de 4 milhões de USDT (PEPE 4,5M)
    binance = ccxt.binance()
    
    while True:
        logging.info("Iniciando nova rodada de monitoramento de ATH")
        symbols = await filter_symbols_by_daily_volume(binance, min_daily_volume)
        
        near_ath_symbols = []
        passed_ath_symbols = []
        
        for symbol in symbols:
            try:
                ticker = await get_binance_data(binance, symbol)
                current_price = ticker['last']
                ath_price = ticker['high']
                
                # Considerando que o ATH é o maior valor histórico registrado
                if current_price >= 0.98 * ath_price:
                    now = datetime.now()
                    ath_time = datetime.fromtimestamp(ticker['timestamp'] / 1000)
                    
                    if current_price > ath_price and (now - ath_time) < timedelta(hours=1):
                        passed_ath_symbols.append(
                            f"{symbol} acabou de ultrapassar o ATH!\n"
                            f"ATH anterior: {ath_price:.8f} USDT\n"
                            f"Preço atual: {current_price:.8f} USDT"
                        )
                    else:
                        near_ath_symbols.append(
                            f"{symbol} está a 2% ou menos de atingir o ATH!\n"
                            f"ATH anterior: {ath_price:.8f} USDT\n"
                            f"Preço atual: {current_price:.8f} USDT"
                        )
                
            except Exception as e:
                logging.error(f"Erro ao processar {symbol}: {e}")
        
        # Enviar mensagens consolidadas
        if passed_ath_symbols:
            passed_message = "Criptomoedas que ultrapassaram o ATH nos últimos 60 minutos:\n" + "\n\n".join(passed_ath_symbols)
            await send_telegram_message(passed_message)
        
        if near_ath_symbols:
            near_message = "Criptomoedas próximas de atingir o ATH:\n" + "\n\n".join(near_ath_symbols)
            await send_telegram_message(near_message)
        
        # Aguardar 5 minutos antes da próxima verificação
        logging.info("Aguardando 5 minutos para a próxima rodada de verificação")
        await asyncio.sleep(300)

if __name__ == "__main__":
    # Iniciar o monitoramento de ATH de forma assíncrona
    logging.info("Iniciando o monitoramento de ATH")
    asyncio.run(monitor_ath())
