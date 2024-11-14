from binance.client import Client
from binance.websockets import BinanceSocketManager
from datetime import datetime
from dynamodb_config import save_trade_data

# Inicialize o cliente da Binance
api_key = "YOUR_BINANCE_API_KEY"
api_secret = "YOUR_BINANCE_API_SECRET"
client = Client(api_key, api_secret)

# Função para processar os dados de trade
def process_message(msg):
    if msg['e'] == 'trade':
        # Extraia os dados relevantes do trade
        trade_data = {
            'pair': msg['s'],  # Par de moedas
            'trade_id': str(msg['t']),
            'timestamp': str(datetime.fromtimestamp(msg['T'] / 1000.0)),
            'buyer_is_maker': msg['m'],
            'quantity': float(msg['q']),
            'price': float(msg['p'])
        }

        # Salve os dados no DynamoDB
        save_trade_data(trade_data)

# Inicialize o gerenciador de WebSocket da Binance
bsm = BinanceSocketManager(client)

# Inicialize o socket para o par de moedas desejado
symbol = 'btcusdt'
bsm.start_trade_socket(symbol, process_message)

# Inicie o loop
bsm.start()
