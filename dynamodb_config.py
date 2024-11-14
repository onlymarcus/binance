import boto3
from decimal import Decimal

# Inicialize o cliente do DynamoDB
aws_access_key = "YOUR_AWS_ACCESS_KEY"
aws_secret_key = "YOUR_AWS_SECRET_KEY"
region_name = "us-east-1"

dynamodb = boto3.resource(
    'dynamodb',
    region_name=region_name,
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# Nome da tabela no DynamoDB
table_name = "TradeData"
table = dynamodb.Table(table_name)

def save_trade_data(trade_data):
    # Salve os dados no DynamoDB
    try:
        # Converter Decimal, se necessário
        for key, value in trade_data.items():
            if isinstance(value, float):
                trade_data[key] = Decimal(str(value))
        
        table.put_item(Item=trade_data)
        print(f"Dados inseridos: {trade_data}")
    except Exception as e:
        print(f"Erro ao inserir dados: {e}")
