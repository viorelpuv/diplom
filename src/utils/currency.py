from datetime import date
from typing import Dict
import functools


import functools
from typing import Dict
import json
import urllib.request

@functools.lru_cache(maxsize=1)
def _get_rates() -> Dict[str, float]:
    """Получает актуальные курсы валют от ЦБ РФ."""
    try:
        # Прямой запрос к API ЦБ
        url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        rates = {'RUB': 1.0}
        for code, info in data.get('Valute', {}).items():
            value = info.get('Value', 0)
            nominal = info.get('Nominal', 1)
            if value and nominal:
                rates[code] = float(value) / float(nominal)
        
        print(f"[CURRENCY] Курсы загружены: USD={rates.get('USD')}, EUR={rates.get('EUR')}")
        return rates
        
    except Exception as e:
        print(f"[CURRENCY] Ошибка загрузки курсов: {e}")
        return {'USD': 96.5, 'EUR': 105.3, 'RUB': 1.0}


def get_rate(currency: str) -> float:
    """Возвращает курс рубля к указанной валюте (USD, EUR)."""
    rates = _get_rates()
    return rates.get(currency.upper(), 0)


def format_price(amount_rub: int, to_currency: str = 'RUB') -> str:
    """Форматирует цену в указанной валюте."""
    symbols = {'RUB': '₽', 'USD': '$', 'EUR': '€'}
    symbol = symbols.get(to_currency, '₽')
    
    if to_currency == 'RUB':
        return f"{amount_rub:,} {symbol}".replace(',', ' ')
    
    rate = get_rate(to_currency)
    if rate <= 0:
        return f"{amount_rub:,} {symbol}".replace(',', ' ')
    
    converted = round(amount_rub / rate)
    return f"{converted:,} {symbol}".replace(',', ' ')