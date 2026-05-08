from datetime import date
from typing import Dict
import functools


@functools.lru_cache(maxsize=1)
def _get_rates() -> Dict[str, float]:
    """Получает актуальные курсы валют от ЦБ РФ."""
    try:
        import cbrapi
        
        # Получаем список всех валют
        currencies = cbrapi.get_currencies_list()
        
        rates = {}
        for currency in currencies:
            char_code = getattr(currency, 'charcode', None) or getattr(currency, 'iso', None) or ''
            value = getattr(currency, 'value', None) or getattr(currency, 'rate', 0)
            nominal = getattr(currency, 'nominal', 1)
            
            if char_code and value:
                rates[str(char_code).upper()] = float(value) / float(nominal)
        
        return rates
        
    except Exception as e:
        print(f"[CURRENCY] Ошибка получения курсов: {e}")
        return {
            'USD': 96.5,
            'EUR': 105.3,
        }


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