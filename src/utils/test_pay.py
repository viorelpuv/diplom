# test_pay.py
import requests
import json
import hashlib
from datetime import datetime
from config import LAVA_ID, LAVA_WEBHOOK_KEY, LAVA_PAY_KEY

# ============================================
# НАСТРОЙКИ (замени на свои)
# ============================================
SHOP_ID = LAVA_ID
SECRET_KEY = LAVA_WEBHOOK_KEY

print('=' * 60)
print('ТЕСТ LAVA API')
print('=' * 60)

order_id = f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
payload = {
    'shopId': SHOP_ID,
    'sum': 10.00,
    'orderId': order_id,
    'comment': 'Тестовый платёж',
    'expire': 60,
    'includeService': ['card', 'sbp']
}

# Генерируем подпись
sign_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
payload['signature'] = hashlib.sha256(f"{sign_str}{SECRET_KEY}".encode()).hexdigest()

# ОТЛАДКА: что отправляем
print(f'\nОтладочная информация:')
print(f'Shop ID: {SHOP_ID}')
print(f'Secret Key (первые 5 символов): {SECRET_KEY[:5]}...')
print(f'Payload (без подписи): {json.dumps({k:v for k,v in payload.items() if k != "signature"}, ensure_ascii=False)}')
print(f'Signature: {payload["signature"][:20]}...')

# Запрос
print(f'\nОтправка запроса...')
r = requests.post(
    'https://api.lava.ru/business/invoice/create',
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    json=payload
)

print(f'HTTP статус: {r.status_code}')
print(f'Ответ сервера: {r.text}')