# utils/lava_api.py
import requests
import hashlib
import json
from datetime import datetime
from utils.config import LAVA_ID, LAVA_WEBHOOK_KEY

class LavaAPI:
    """API для работы с платёжной системой LAVA"""
    
    BASE_URL = "https://api.lava.ru/business"
    
    def __init__(self):
        self.shop_id = LAVA_ID
        self.secret_key = LAVA_WEBHOOK_KEY
    
    def _generate_signature(self, data):
        """Генерирует подпись для запроса"""
        sign_string = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(f"{sign_string}{self.secret_key}".encode()).hexdigest()
    
    def _make_request(self, endpoint, payload):
        """Базовый метод для запросов к API"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Добавляем подпись в тело запроса
        payload["shopId"] = self.shop_id
        payload["signature"] = self._generate_signature(payload)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            return response.json()
        except requests.RequestException as e:
            print(f"❌ LAVA API error: {e}")
            return {"status_check": False, "error": str(e)}
    
    def create_invoice(self, amount, order_id, success_url=None, fail_url=None, 
                       hook_url=None, comment=None, expire=300, include_service=None):
        """
        Создание счёта на оплату
        
        Args:
            amount (float): Сумма платежа
            order_id (str): Уникальный ID заказа в вашей системе
            success_url (str): URL при успешной оплате
            fail_url (str): URL при неуспешной оплате
            hook_url (str): URL для вебхуков
            comment (str): Комментарий к счёту
            expire (int): Время жизни счёта в минутах (макс 5 дней)
            include_service (list): Методы оплаты ['card', 'sbp', 'qiwi']
        
        Returns:
            dict: Ответ API с url оплаты или ошибкой
        """
        payload = {
            "sum": float(amount),
            "orderId": str(order_id),
            "expire": expire
        }
        
        if success_url:
            payload["successUrl"] = success_url
        if fail_url:
            payload["failUrl"] = fail_url
        if hook_url:
            payload["hookUrl"] = hook_url
        if comment:
            payload["comment"] = comment
        if include_service:
            payload["includeService"] = include_service
        
        return self._make_request("invoice/create", payload)
    
    def get_invoice_status(self, invoice_id):
        """
        Проверка статуса счёта
        
        Args:
            invoice_id (str): ID счёта в LAVA
        
        Returns:
            dict: Статус счёта
        """
        payload = {"invoiceId": invoice_id}
        return self._make_request("invoice/status", payload)
    
    def get_balance(self):
        """
        Получение баланса кошелька
        
        Returns:
            dict: Информация о балансе
        """
        payload = {}
        return self._make_request("wallet/balance", payload)


# ============================================
# ТЕСТЫ LAVA API
# ============================================
def test_lava_api():
    """Тестирование API LAVA"""
    
    # ⚠️ ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ДАННЫЕ ИЗ ЛИЧНОГО КАБИНЕТА
    SHOP_ID = "ваш_shop_id_uuid"
    SECRET_KEY = "ваш_секретный_ключ"
    
    lava = LavaAPI(SHOP_ID, SECRET_KEY)
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ LAVA API")
    print("=" * 60)
    
    # Тест 1: Создание счёта
    print("\n📝 Тест 1: Создание счёта на оплату")
    test_order_id = f"BRT-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    result = lava.create_invoice(
        amount=10.00,
        order_id=test_order_id,
        comment="Тестовый платёж BRT",
        expire=60,
        include_service=["card", "sbp"]
    )
    
    if result.get("status_check"):
        invoice_id = result["data"]["id"]
        payment_url = result["data"]["url"]
        amount = result["data"]["amount"]
        status = result["data"]["status"]
        
        print(f"✅ Счёт создан успешно!")
        print(f"   ID счёта: {invoice_id}")
        print(f"   Сумма: {amount} ₽")
        print(f"   Статус: {status} (0 - ожидает оплаты)")
        print(f"   URL оплаты: {payment_url}")
        print(f"\n   🔗 Откройте ссылку для тестовой оплаты:")
        print(f"   {payment_url}")
    else:
        print(f"❌ Ошибка создания счёта:")
        print(f"   {result.get('error')}")
        return
    
    # Тест 2: Проверка статуса счёта
    print("\n📝 Тест 2: Проверка статуса счёта")
    
    status_result = lava.get_invoice_status(invoice_id)
    
    if status_result.get("status_check"):
        status_data = status_result["data"]
        print(f"✅ Статус получен:")
        print(f"   ID: {status_data.get('id')}")
        print(f"   Статус: {status_data.get('status')}")
        print(f"   Сумма: {status_data.get('amount')} ₽")
    else:
        print(f"❌ Ошибка получения статуса: {status_result.get('error')}")
    
    # Тест 3: Проверка баланса
    print("\n📝 Тест 3: Проверка баланса")
    
    balance_result = lava.get_balance()
    
    if balance_result.get("status_check"):
        balance_data = balance_result["data"]
        print(f"✅ Баланс получен:")
        print(f"   Баланс RUB: {balance_data.get('balance_rub', 'Н/Д')} ₽")
        print(f"   Баланс USD: {balance_data.get('balance_usd', 'Н/Д')} $")
    else:
        print(f"ℹ️ Баланс: {balance_result.get('error', 'Недоступно')}")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\n💡 Для тестовой оплаты используйте:")
    print("   Карта: 4111 1111 1111 1111")
    print("   Срок: любой будущий (например, 12/30)")
    print("   CVV: любой (например, 123)")
    print(f"\n   Или откройте ссылку: {payment_url}")


# ============================================
# ИНТЕГРАЦИЯ С FLASK
# ============================================
def create_payment_for_order(order_number, amount, user_email=None):
    """
    Создаёт платёж для заказа в BRT
    
    Args:
        order_number (str): Номер заказа BRT-20260510...
        amount (float): Сумма к оплате
        user_email (str): Email пользователя
    
    Returns:
        dict: {'success': bool, 'payment_url': str, 'invoice_id': str}
    """
    from flask import url_for
    
    SHOP_ID = "ваш_shop_id"
    SECRET_KEY = "ваш_секретный_ключ"
    
    lava = LavaAPI(SHOP_ID, SECRET_KEY)
    
    result = lava.create_invoice(
        amount=amount,
        order_id=order_number,
        comment=f"Оплата заказа {order_number}",
        success_url=url_for('payment_success', order=order_number, _external=True),
        fail_url=url_for('payment_fail', order=order_number, _external=True),
        hook_url=url_for('lava_webhook', _external=True),
        expire=300,
        include_service=["card", "sbp"]
    )
    
    if result.get("status_check"):
        return {
            "success": True,
            "payment_url": result["data"]["url"],
            "invoice_id": result["data"]["id"]
        }
    
    return {"success": False, "error": result.get("error")}


if __name__ == "__main__":
    test_lava_api()