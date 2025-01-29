#API_TOKEN = "7576886054:AAF4ct9NvH81Us7k05d3LSXO6zrolJW-oC0"

import logging
import numpy as np
import matplotlib.pyplot as plt
import io
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import ccxt
from cachetools import TTLCache
import requests
import dotenv
from os import getenv
import ccxt.async_support as ccxt

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializa o bot do Telegram

dotenv.load_dotenv()
CHAVE_API = getenv("API_TOKEN")
bot = Bot(token=CHAVE_API)
dp = Dispatcher(bot)

# Inicializa a exchange Binance
async def get_exchange():
    """Retorna uma instância da exchange Binance (versão assíncrona)."""
    return ccxt.binance()

async def close_exchange(exchange):
    """Fecha corretamente a instância da exchange."""
    if exchange:
        await exchange.close()

# Configuração do cache
cache = TTLCache(maxsize=100, ttl=300)  # Cache com TTL de 5 minutos (300 segundos)

# Função para calcular a SMA (Simple Moving Average)
def calcular_sma(precos, periodo):
    """Calcula a SMA para uma lista de preços."""
    return np.mean(precos[-periodo:])

# Função para calcular o RSI (Relative Strength Index)
def calcular_rsi(precos, periodo=14):
    """Calcula o RSI para uma lista de preços."""
    deltas = np.diff(precos)
    ganhos = np.where(deltas > 0, deltas, 0)
    perdas = np.where(deltas < 0, -deltas, 0)
    media_ganhos = np.mean(ganhos[-periodo:])
    media_perdas = np.mean(perdas[-periodo:])
    if media_perdas == 0:
        return 100
    rs = media_ganhos / media_perdas
    return 100 - (100 / (1 + rs))

# Função para calcular o MACD (Moving Average Convergence Divergence)
def calcular_macd(precos, periodo_curto=12, periodo_longo=26, periodo_sinal=9):
    """Calcula o MACD e a linha de sinal."""
    ema_curta = np.mean(precos[-periodo_curto:])
    ema_longa = np.mean(precos[-periodo_longo:])
    macd = ema_curta - ema_longa
    sinal = np.mean(precos[-periodo_sinal:])
    return macd, sinal

def identificar_suporte_resistencia(precos, fator=1):
    """Identifica níveis de suporte e resistência com base no desvio padrão."""
    desvio = np.std(precos) * fator
    suporte = min(precos) - desvio
    resistencia = max(precos) + desvio
    return suporte, resistencia

# Comando /sr
@dp.message_handler(commands=['sr'])
async def comando_suporte_resistencia(message: types.Message):
    """Comando /sr: Calcula suporte e resistência para o símbolo escolhido."""
    exchange = await get_exchange()
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /sr <symbol> (e.g., /sr BTC/BRL)")
            return
        
        symbol = args[1].upper()
        
        # Verifica se o símbolo contém uma barra (/)
        if '/' not in symbol:
            await message.reply("Invalid symbol format. Use '/' to separate currencies (e.g., BTC/BRL).")
            return
        
        # Extrai a moeda de cotação (por exemplo, BRL em BTC/BRL)
        moeda_cotacao = symbol.split('/')[1]
        
        # Obtém os últimos 72 candles de 1 hora
        candles = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=72)
        if not candles:
            await message.reply(f"No data found for {symbol}.")
            return
        
        # Extrai os preços de fechamento
        precos = [candle[4] for candle in candles]
        
        # Calcula suporte e resistência
        suporte, resistencia = identificar_suporte_resistencia(precos, fator=1)
        
        # Responde ao usuário
        resposta = (
            f"Support and Resistance for {symbol} (last 72 hours):\n"
            f"📉 Support: {suporte:.2f} {moeda_cotacao}\n"
            f"📈 Resistance: {resistencia:.2f} {moeda_cotacao}"
        )
        await message.reply(resposta)
    except Exception as e:
        logger.error(f"Error in /sr command: {e}")
        await message.reply("Error calculating support and resistance.")
    finally:
        await close_exchange(exchange)  # Fecha a exchange
        
# Função para identificar tendência com SMA, RSI e MACD
async def identificar_tendencia(symbol, timeframe='1h', short_period=9, long_period=21, rsi_period=14):
    """Identifica a tendência com base em SMA, RSI e MACD."""
    exchange = await get_exchange()
    try:
        # Verifica se os dados estão no cache
        cache_key = f"tendencia_{symbol}_{timeframe}"
        if cache_key in cache:
            return cache[cache_key]
        
        # Obtém os dados históricos (candles)
        candles = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=long_period + rsi_period)
        if not candles:
            return None
        
        # Extrai os preços de fechamento
        precos = [candle[4] for candle in candles]
        
        # Calcula as SMAs
        sma_curta = calcular_sma(precos, short_period)
        sma_longa = calcular_sma(precos, long_period)
        
        # Calcula o RSI
        rsi = calcular_rsi(precos, rsi_period)
        
        # Calcula o MACD
        macd, sinal = calcular_macd(precos)
        
        # Determina a tendência
        if sma_curta > sma_longa and macd > sinal and rsi > 50:
            tendencia = "uptrend"
        elif sma_curta < sma_longa and macd < sinal and rsi < 50:
            tendencia = "downtrend"
        else:
            tendencia = "neutral"
        
        # Armazena no cache
        cache[cache_key] = tendencia
        return tendencia
    except Exception as e:
        logger.error(f"Error identifying trend for {symbol}: {e}")
        return None
    finally:
        await close_exchange(exchange)

# Função para gerar gráfico diário
async def gerar_grafico(symbol, timeframe='1d', limit=30):
    """Gera um gráfico de preços diários."""
    exchange = await get_exchange()
    try:
        # Verifica se o gráfico está no cache
        cache_key = f"grafico_{symbol}_{timeframe}"
        if cache_key in cache:
            return cache[cache_key]
        
        candles = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not candles:
            return None
        
        # Extrai os preços de fechamento
        precos = [candle[4] for candle in candles]
        
        # Gera o gráfico
        plt.figure(figsize=(10, 5))
        plt.plot(precos, label='Price')
        plt.title(f"{symbol} Price Chart ({timeframe})")
        plt.xlabel("Time")
        plt.ylabel("Price (USDT)")
        plt.legend()
        
        # Salva o gráfico em um buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        # Armazena no cache
        cache[cache_key] = buf
        return buf
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {e}")
        return None
    finally:
        await close_exchange(exchange)

# Comandos do bot
@dp.message_handler(commands=['start'])
async def comando_start(message: types.Message):
    """Comando /start: Mensagem de boas-vindas."""
    await message.reply("Hello! Welcome to CryptoBot. Use the commands to get information about cryptocurrencies.")

@dp.message_handler(commands=['uptrend'])
async def comando_tendencia_alta(message: types.Message):
    """Comando /uptrend: Mostra criptomoedas em tendência de alta."""
    exchange = await get_exchange()
    try:
        # Obtém todos os tickers da Binance
        tickers = await exchange.fetch_tickers()
        
        # Filtra criptomoedas com volume maior que 200 milhões
        criptos_alta = []
        for symbol, ticker in tickers.items():
            if ticker['quoteVolume'] > 200000000:  # Filtra por volume
                tendencia = await identificar_tendencia(symbol)
                if tendencia == "uptrend":
                    criptos_alta.append(symbol)
        
        if criptos_alta:
            resposta = "Cryptocurrencies in uptrend:\n" + "\n".join(criptos_alta)
        else:
            resposta = "No cryptocurrencies in uptrend at the moment."
        
        await message.reply(resposta)
    except Exception as e:
        logger.error(f"Error in /uptrend command: {e}")
        await message.reply("Error fetching uptrend data.")
    finally:
        await close_exchange(exchange)

@dp.message_handler(commands=['downtrend'])
async def comando_tendencia_baixa(message: types.Message):
    """Comando /downtrend: Mostra criptomoedas em tendência de baixa."""
    exchange = await get_exchange()
    try:
        # Obtém todos os tickers da Binance
        tickers = await exchange.fetch_tickers()
        
        # Filtra criptomoedas com volume maior que 200 milhões
        criptos_baixa = []
        for symbol, ticker in tickers.items():
            if ticker['quoteVolume'] > 200000000:  # Filtra por volume
                tendencia = await identificar_tendencia(symbol)
                if tendencia == "downtrend":
                    criptos_baixa.append(symbol)
        
        if criptos_baixa:
            resposta = "Cryptocurrencies in downtrend:\n" + "\n".join(criptos_baixa)
        else:
            resposta = "No cryptocurrencies in downtrend at the moment."
        
        await message.reply(resposta)
    except Exception as e:
        logger.error(f"Error in /downtrend command: {e}")
        await message.reply("Error fetching downtrend data.")
    finally:
        await close_exchange(exchange)

@dp.message_handler(commands=['price'])
async def comando_preco_atual(message: types.Message):
    """Comando /price: Mostra o preço atual de uma criptomoeda."""
    exchange = await get_exchange()
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /price <symbol> (e.g., /price BTC/USDT)")
            return
        
        symbol = args[1].upper()
        ticker = await exchange.fetch_ticker(symbol)
        preco_atual = ticker['last']
        await message.reply(f"Current price of {symbol}: {preco_atual} ")
    except Exception as e:
        logger.error(f"Error in /price command: {e}")
        await message.reply("Error fetching price data.")
    finally:
        await close_exchange(exchange)

@dp.message_handler(commands=['chart'])
async def comando_grafico(message: types.Message):
    """Comando /chart: Envia o gráfico diário de uma criptomoeda."""
    exchange = await get_exchange()
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /chart <symbol> (e.g., /chart BTC/USDT)")
            return
        
        symbol = args[1].upper()
        grafico = await gerar_grafico(symbol)
        if grafico:
            await message.reply_photo(grafico)
        else:
            await message.reply("Error generating chart.")
    except Exception as e:
        logger.error(f"Error in /chart command: {e}")
        await message.reply("Error generating chart.")
    finally:
        await close_exchange(exchange)

@dp.message_handler(commands=['high'])
async def comando_24h_high(message: types.Message):
    """Comando /24hhigh: Mostra a máxima das últimas 24 horas de uma criptomoeda."""
    exchange = await get_exchange()
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Uso: /high <symbol> (ex: /high BTC/USDT)")
            return
        
        symbol = args[1].upper()
        ticker = await exchange.fetch_ticker(symbol)
        high_24h = ticker['high']
        
        await message.reply(f"24h High de {symbol}: {high_24h} ")
    except Exception as e:
        logger.error(f"Erro no comando /high: {e}")
        await message.reply("Erro ao buscar 24h High.")
    finally:
        await close_exchange(exchange)

@dp.message_handler(commands=['low'])
async def comando_24h_low(message: types.Message):
    """Comando /24hlow: Mostra a mínima das últimas 24 horas de uma criptomoeda."""
    exchange = await get_exchange()
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Uso: /low <symbol> (ex: /low BTC/USDT)")
            return
        
        symbol = args[1].upper()
        ticker = await exchange.fetch_ticker(symbol)
        low_24h = ticker['low']
        
        await message.reply(f"24h Low de {symbol}: {low_24h} ")
    except Exception as e:
        logger.error(f"Erro no comando /low: {e}")
        await message.reply("Erro ao buscar 24h Low.")
    finally:
        await close_exchange(exchange)

# Inicia o bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)