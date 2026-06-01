import random
import json
import threading
import time
from datetime import datetime, date
from functools import wraps

from flask import Flask, abort, jsonify, render_template, request, redirect, g, make_response, session
from flask_babel import Babel, _

from utils.rail_api import RZDApi
from utils.currency import format_price
from utils.database.database import (
    add_bonus_points, apply_promocode, calculate_loyalty_level, check_promocode, get_all_trips_with_details, get_tickets_by_order_number, get_user_total_spent, init_db, save_passenger, create_order, save_ticket, 
    save_transaction, update_order_status, save_train_full, 
    get_order_by_number, get_user_by_document, register_user,
    login_user, save_login_history, get_user_by_id,
    update_profile, change_password, get_user_tickets,
    get_user_login_history, get_user_bonus,
    is_admin, get_dashboard_stats, get_all_orders,
    get_all_users, get_all_trains, get_all_stations,
    get_all_tickets, get_all_admins, delete_promocode, 
    get_admin_logs, toggle_user_active, add_admin, remove_admin, 
    get_sales_report, get_all_promocodes, create_promocode, update_order_promo,
    get_tickets_by_date, save_admin_action, get_admin_actions, update_user_loyalty,
    reserve_seats, release_seats, release_expired_orders, get_ticket_by_number
)

app = Flask(__name__)
app.secret_key = "12432dsacOIAJWoDj98918u383jodpsSPOAsc"

api = RZDApi()

init_db()

WAGON_TYPES = {
    'sitting': 'Сидячий',
    'reserved_seat': 'Плацкарт',
    'compartment': 'Купе',
    'luxury': 'Люкс',
    'soft': 'Мягкий',
    'sv': 'СВ'
}


@app.context_processor
def inject_utils():
    from utils.currency import get_rate
    return dict(get_rate=get_rate)


@app.before_request
def set_lang_currency():
    lang = request.args.get('lang') or request.cookies.get('brt_lang') or 'ru'
    g.lang = lang
    
    cur = request.args.get('cur') or request.cookies.get('brt_cur') or 'RUB'
    g.cur = cur


@app.template_filter('convert_price')
def convert_price(price_rub):
    if not price_rub or price_rub == 0:
        return 0
    
    currency = getattr(g, 'cur', 'RUB')
    
    if currency == 'RUB':
        return int(price_rub)
    
    try:
        from utils.currency import get_rate
        rate = get_rate(currency)
        if rate and rate > 0:
            converted = float(price_rub) / rate
            return int(round(converted))
    except Exception as e:
        print(f"[CONVERT] Ошибка: {e}")
    
    return int(price_rub)


@app.template_filter('currency_symbol')
def currency_symbol(dummy=None):
    currency = getattr(g, 'cur', 'RUB')
    symbols = {'RUB': '₽', 'USD': '$', 'EUR': '€'}
    return symbols.get(currency, '₽')


def build_prices_from_cars(cars_data):
    """Собирает словарь prices из CarGroups или Cars, группируя по типу вагона."""
    grouped = {}
    
    for car in cars_data:
        car_type = car.get('CarTypeName', '') or ''
        class_name = car.get('ServiceClassNameRu', car.get('ServiceClassName', '')) or ''
        price = car.get('MinPrice', car.get('Price', 0)) or 0
        free_seats = car.get('TotalPlaceQuantity', 0) or 0
        if free_seats == 0:
            free_seats = sum([
                car.get('PlaceQuantity', 0) or 0,
                car.get('LowerPlaceQuantity', 0) or 0,
                car.get('UpperPlaceQuantity', 0) or 0,
                car.get('LowerSidePlaceQuantity', 0) or 0,
                car.get('UpperSidePlaceQuantity', 0) or 0,
            ])
        
        if free_seats <= 0:
            continue
        
        wagon_type = 'sitting'
        ct = (car_type or '').lower()
        if 'плац' in ct: wagon_type = 'reserved_seat'
        elif 'купе' in ct: wagon_type = 'compartment'
        elif 'св' in ct: wagon_type = 'sv'
        elif 'люкс' in ct: wagon_type = 'luxury'
        elif 'мягк' in ct: wagon_type = 'soft'
        
        if price <= 0:
            price = 0
        
        if wagon_type not in grouped:
            grouped[wagon_type] = {
                'wagon_type': wagon_type,
                'wagon_name': WAGON_TYPES.get(wagon_type, car_type or ''),
                'class': 'economy',
                'class_name': class_name or 'economy',
                'price': price,
                'free_seats': free_seats,
                'total_seats': free_seats,
            }
        else:
            grouped[wagon_type]['free_seats'] += free_seats
            grouped[wagon_type]['total_seats'] += free_seats
            if price > 0 and (grouped[wagon_type]['price'] == 0 or price < grouped[wagon_type]['price']):
                grouped[wagon_type]['price'] = price
                grouped[wagon_type]['class_name'] = class_name or 'economy'
    
    return grouped


def get_min_price(prices):
    mp = None
    for p in prices.values():
        if p['price'] > 0 and (mp is None or p['price'] < mp):
            mp = p['price']
    return mp


def check_seats(prices, total_passengers):
    for p in prices.values():
        if p['free_seats'] >= total_passengers:
            return True
    return False


def format_train(train, from_city, to_city, total_passengers):
    trip = api.format_trip_for_card(train)
    if not trip.get('train_number'):
        return None
    
    dep_str = trip.get('departure_datetime', '')
    arr_str = trip.get('arrival_datetime', '')
    try:
        dep_dt = datetime.fromisoformat(dep_str) if dep_str else datetime.now()
        arr_dt = datetime.fromisoformat(arr_str) if arr_str else datetime.now()
    except:
        dep_dt = datetime.now()
        arr_dt = datetime.now()
    
    car_groups = train.get('CarGroups', [])
    cars = trip.get('cars', [])
    prices = build_prices_from_cars(car_groups if car_groups else cars)
    
    if total_passengers > 0 and not check_seats(prices, total_passengers):
        return None
    
    min_price = get_min_price(prices)
    
    transfers = train.get('Transfers', [])
    transfer_count = len(transfers) if transfers else (1 if trip.get('has_transfer') else 0)
    
    days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
    
    return {
        'trip_id': trip.get('trip_id', abs(hash(f"{trip.get('train_number')}_{dep_dt}"))),
        'date': dep_dt.strftime('%Y-%m-%d'),
        'departure': dep_dt.strftime('%H:%M'),
        'arrival': arr_dt.strftime('%H:%M'),
        'day_dep': dep_dt.strftime('%d'),
        'month_dep': dep_dt.strftime('%m'),
        'day_of_week_dep': days[dep_dt.weekday()],
        'day_arr': arr_dt.strftime('%d'),
        'month_arr': arr_dt.strftime('%m'),
        'day_of_week_arr': days[arr_dt.weekday()],
        'from_station': trip.get('from_station', from_city),
        'from_city': from_city,
        'to_station': trip.get('to_station', to_city),
        'to_city': to_city,
        'train_number': trip.get('train_number', ''),
        'train_name': trip.get('train_name', ''),
        'duration': api.format_duration(trip.get('duration_minutes', 0)),
        'transfer_count': transfer_count,
        'source': 'api',
        'prices': prices,
        'min_price': min_price,
        'schemes': trip.get('schemes', None),
    }

def cleanup_expired_orders():
    """Фоновая очистка истёкших заказов."""
    while True:
        try:
            count = release_expired_orders()
            if count > 0:
                print(f"[CLEANUP] Освобождено {count} истёкших заказов")
        except Exception as e:
            print(f"[CLEANUP] Ошибка: {e}")
        time.sleep(60)  # Проверка каждую минуту

# Запускаем в фоновом потоке
cleanup_thread = threading.Thread(target=cleanup_expired_orders, daemon=True)
cleanup_thread.start()


@app.route('/')
def main():
    today = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', today=today)


@app.route('/search')
def search():
    from_city = request.args.get('from', '').strip()
    to_city = request.args.get('to', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    adults = request.args.get('adults', '1')
    children = request.args.get('children', '0')
    infants = request.args.get('infants', '0')
    total_passengers = int(adults) + int(children)
    
    if date_to and date_from:
        if date_to < date_from:
            date_to = date_from
    
    print(f"\n{'='*60}")
    print(f"ПОИСК: from='{from_city}' to='{to_city}' date_from='{date_from}' date_to='{date_to}' passengers={total_passengers}")
    print(f"{'='*60}")
    
    if not from_city or not to_city:
        return render_template(
            'search.html',
            results=[], return_results=[],
            from_city=from_city, to_city=to_city,
            date_from=date_from, date_to=date_to,
            adults=adults, children=children, infants=infants,
            wagon_types=WAGON_TYPES,
            message='Введите город отправления и город прибытия'
        )
    
    if not date_from:
        date_from = date.today().strftime('%Y-%m-%d')
    
    try:
        return_date = date_to if date_to and date_to != date_from else None
        
        tickets_data = api.search_tickets(
            from_station=from_city,
            to_station=to_city,
            departure_date=date_from,
            return_date=return_date
        )
        
        forward_trains = []
        backward_trains = []
        
        if isinstance(tickets_data, list):
            forward_trains = tickets_data
        elif isinstance(tickets_data, dict):
            fwd = tickets_data.get('forward', [])
            bwd = tickets_data.get('back', [])
            forward_trains = fwd if isinstance(fwd, list) else []
            backward_trains = bwd if isinstance(bwd, list) else []
        
        print(f"  Поездов туда: {len(forward_trains)}, обратно: {len(backward_trains)}")
        
        results = []
        for train in forward_trains:
            formatted = format_train(train, from_city, to_city, total_passengers)
            if formatted:
                real_trip_id = save_train_full(formatted, from_city, to_city)
                if real_trip_id:
                    formatted['trip_id'] = real_trip_id
                results.append(formatted)
        
        return_results = []
        for train in backward_trains:
            formatted = format_train(train, to_city, from_city, total_passengers)
            if formatted:
                formatted['from_station'], formatted['to_station'] = formatted['to_station'], formatted['from_station']
                return_results.append(formatted)
                try:
                    save_train_full(formatted, to_city, from_city)
                except:
                    pass
        
        print(f"  Итого: туда={len(results)}, обратно={len(return_results)}")
        
        if not results and not return_results:
            msg = 'Билеты не найдены.'
            if forward_trains:
                msg = f'Нет мест на {total_passengers} пасс. Попробуйте уменьшить количество.'
            return render_template(
                'search.html',
                results=[], return_results=[],
                from_city=from_city, to_city=to_city,
                date_from=date_from, date_to=date_to,
                adults=adults, children=children, infants=infants,
                wagon_types=WAGON_TYPES,
                message=msg
            )
        
        return render_template(
            'search.html',
            results=results,
            return_results=return_results,
            from_city=from_city,
            to_city=to_city,
            date_from=date_from,
            date_to=date_to,
            adults=adults,
            children=children,
            infants=infants,
            wagon_types=WAGON_TYPES,
            message=None
        )
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            'search.html',
            results=[], return_results=[],
            from_city=from_city, to_city=to_city,
            date_from=date_from, date_to=date_to,
            adults=adults, children=children, infants=infants,
            wagon_types=WAGON_TYPES,
            message=f'Ошибка при поиске: {str(e)}'
        )


@app.template_filter('month_name')
def month_name(month_num):
    months = {
        '01': 'янв', '02': 'фев', '03': 'мар',
        '04': 'апр', '05': 'мая', '06': 'июн',
        '07': 'июл', '08': 'авг', '09': 'сен',
        '10': 'окт', '11': 'ноя', '12': 'дек'
    }
    return months.get(month_num, '')


@app.route('/api/quick-search')
def api_quick_search():
    from_city = request.args.get('from', '').strip()
    to_city = request.args.get('to', '').strip()
    date_from = request.args.get('date', '').strip()
    
    if not from_city or not to_city:
        return {'min_price': None}
    
    try:
        tickets_data = api.search_tickets(
            from_station=from_city,
            to_station=to_city,
            departure_date=date_from
        )
        
        trains = []
        if isinstance(tickets_data, list):
            trains = tickets_data
        elif isinstance(tickets_data, dict):
            trains = tickets_data.get('forward', [])
        
        min_price = None
        for train in trains:
            formatted = format_train(train, from_city, to_city, 1)
            if formatted and formatted.get('min_price'):
                price = int(formatted['min_price'])  # округление вниз
                if min_price is None or price < min_price:
                    min_price = price
        
        return {'min_price': min_price}
    except:
        return {'min_price': None}


@app.route('/select-seats')
def select_seats():
    from_city = (request.args.get('from') or '').strip()
    to_city = (request.args.get('to') or '').strip()
    date_from = (request.args.get('date_from') or '').strip()
    date_to = (request.args.get('date_to') or '').strip()
    trip_index = request.args.get('trip_index', '0')
    return_trip_index = request.args.get('return_trip_index', '')
    adults = int(request.args.get('adults', 1))
    children = int(request.args.get('children', 0))
    infants = int(request.args.get('infants', 0))
    total_passengers = adults + children

    if not from_city or not to_city:
        return redirect('/')

    try:
        trip_idx = int(trip_index)
    except:
        trip_idx = 0

    try:
        ret_idx = int(return_trip_index) if return_trip_index else None
    except:
        ret_idx = None

    try:
        return_date = date_to if date_to and date_to != date_from else None

        tickets_data = api.search_tickets(
            from_station=from_city,
            to_station=to_city,
            departure_date=date_from,
            return_date=return_date
        )

        forward_trains = []
        backward_trains = []

        if isinstance(tickets_data, list):
            forward_trains = tickets_data
        elif isinstance(tickets_data, dict):
            fwd = tickets_data.get('forward', [])
            bwd = tickets_data.get('back', [])
            forward_trains = fwd if isinstance(fwd, list) else []
            backward_trains = bwd if isinstance(bwd, list) else []

        results = []
        for train in forward_trains:
            formatted = format_train(train, from_city, to_city, total_passengers)
            if formatted:
                real_trip_id = save_train_full(formatted, from_city, to_city)
                if real_trip_id:
                    formatted['trip_id'] = real_trip_id
                results.append(formatted)

        return_results = []
        for train in backward_trains:
            formatted = format_train(train, to_city, from_city, total_passengers)
            if formatted:
                formatted['from_station'], formatted['to_station'] = formatted['to_station'], formatted['from_station']
                real_trip_id = save_train_full(formatted, to_city, from_city)
                if real_trip_id:
                    formatted['trip_id'] = real_trip_id
                return_results.append(formatted)

        trip = results[trip_idx] if 0 <= trip_idx < len(results) else (results[0] if results else None)
        return_trip = return_results[ret_idx] if ret_idx is not None and 0 <= ret_idx < len(return_results) else (return_results[0] if ret_idx is not None and return_results else None)

        if not trip:
            return "Билет не найден", 404

        total_price = (trip.get('min_price') or 0) + (return_trip.get('min_price') or 0 if return_trip else 0)

        return render_template(
            'select_seats.html',
            trip=trip,
            return_trip=return_trip,
            total_price=total_price,
            adults=adults,
            children=children,
            infants=infants,
            from_city=from_city,
            to_city=to_city,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        print(f"Ошибка в select_seats: {e}")
        return f"Ошибка: {str(e)}", 500


@app.template_filter('day_of_week')
def day_of_week(date_str):
    if not date_str:
        return ''
    try:
        days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        dt = datetime.fromisoformat(date_str.strip()) if 'T' in str(date_str) else datetime.strptime(date_str.strip(), '%Y-%m-%d')
        return days[dt.weekday()]
    except:
        return ''


@app.template_filter('short_station')
def short_station(name):
    if not name:
        return ''
    return name.split('(')[0].strip()


@app.template_filter('group_wagons')
def group_wagons(prices):
    grouped = {}
    for key, data in prices.items():
        wt = data.get('wagon_type', key)
        if wt not in grouped:
            grouped[wt] = {
                'wagon_type': wt,
                'wagon_name': data.get('wagon_name', ''),
                'price': data.get('price', 0),
                'free_seats': data.get('free_seats', 0)
            }
        else:
            grouped[wt]['free_seats'] += data.get('free_seats', 0)
            if data.get('price', 0) > 0 and data.get('price', 0) < grouped[wt]['price']:
                grouped[wt]['price'] = data['price']
    return grouped


@app.route('/api/wagon-scheme')
def api_wagon_scheme():
    wagon_type = request.args.get('wagon_type', '')
    train_number = request.args.get('train_number', '')
    free_seats = int(request.args.get('free_seats', 36))
    total_seats = int(request.args.get('total_seats', 54))
    
    seed_str = f"{train_number}_{wagon_type}"
    
    prices_data = {
        wagon_type: {
            'wagon_type': wagon_type,
            'free_seats': free_seats,
            'total_seats': total_seats,
        }
    }
    
    result = generate_interactive_scheme(wagon_type, prices_data, seed_str)
    
    return {'success': True, 'scheme_html': result}


@app.route('/api/currency-rates')
def api_currency_rates():
    from utils.currency import get_rate
    return {
        'RUB': 1,
        'USD': get_rate('USD'),
        'EUR': get_rate('EUR'),
    }


def generate_interactive_scheme(wagon_type, prices_data=None, seed_str=''):
    total_free = 22
    total_all = 36
    
    if prices_data:
        for key, data in prices_data.items():
            if data.get('wagon_type') == wagon_type:
                total_free = data.get('free_seats', total_free)
                total_all = data.get('total_seats', total_all)
                break
    
    wagon_capacity = {
        'reserved_seat': 54, 'compartment': 36, 'sitting': 60,
        'luxury': 18, 'sv': 18, 'soft': 18
    }
    seats_per_wagon = wagon_capacity.get(wagon_type, 36)
    num_wagons = max(1, (total_free + seats_per_wagon - 1) // seats_per_wagon)
    
    import hashlib, random
    
    html = f'<div class="scheme-container" style="padding: 20px;">'
    html += f'<h4 style="text-align:center;margin-bottom:10px;">{WAGON_TYPES.get(wagon_type, "Вагон")}</h4>'
    html += f'<p style="text-align:center;color:#A3A3A3;margin-bottom:15px;">Свободно {total_free} мест ({num_wagons} ваг.)</p>'
    
    free_left = total_free
    
    for wagon_num in range(1, num_wagons + 1):
        wagon_free = min(seats_per_wagon, free_left)
        wagon_occupied = seats_per_wagon - wagon_free
        
        wagon_seed = int(hashlib.md5(f"{seed_str}_w{wagon_num}".encode()).hexdigest()[:8], 16)
        wagon_rng = random.Random(wagon_seed)
        
        all_seats = list(range(1, seats_per_wagon + 1))
        wagon_rng.shuffle(all_seats)
        occupied_seats = set(all_seats[:wagon_occupied])
        
        html += f'<div style="text-align:center;margin-top:20px;margin-bottom:5px;font-weight:600;font-size:16px;color:#1E1E1E;">Вагон {wagon_num}</div>'
        html += f'<p style="text-align:center;color:#A3A3A3;font-size:13px;margin-bottom:10px;">Свободно {wagon_free} из {seats_per_wagon}</p>'
        
        for row in range(9):
            html += '<div class="scheme-row" style="display:flex;gap:8px;justify-content:center;margin-bottom:8px;">'
            html += f'<span style="width:30px;color:#A3A3A3;font-size:14px;text-align:right;line-height:44px;">{row+1}</span>'
            for col in range(4):
                seat_num = row * 4 + col + 1
                if seat_num > seats_per_wagon: break
                is_occ = seat_num in occupied_seats
                html += f'<div class="scheme-seat{" scheme-seat--occupied" if is_occ else ""}" data-seat="{seat_num}" data-wagon="{wagon_num}" style="width:44px;height:44px;background:{"#E8E8E8" if is_occ else "#E8F0FE"};border:2px solid {"#BCBCBC" if is_occ else "#4672FF"};border-radius:8px;cursor:{"default" if is_occ else "pointer"};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;color:{"#A3A3A3" if is_occ else "#4672FF"};">{seat_num}</div>'
            html += '</div>'
        
        free_left -= wagon_free
    
    html += '</div>'
    return html


@app.route('/payment')
def payment():
    adults = int(request.args.get('adults', 1))
    children = int(request.args.get('children', 0))
    infants = int(request.args.get('infants', 0))
    
    return render_template(
        'payment.html',
        adults=adults,
        children=children,
        infants=infants,
    )


@app.route('/confirm', methods=['GET', 'POST'])
def confirm():
    if request.method == 'POST':
        import json, random
        
        passengers_data = request.form.get('passengers_data', '{}')
        contact_data = request.form.get('contact_data', '{}')
        seats_json = request.form.get('seats', '{}')
        trip_json = request.form.get('trip_info', '{}')
        promo_code = request.form.get('promo', '').strip().upper()
        
        passengers = json.loads(passengers_data) if passengers_data else []
        contact = json.loads(contact_data) if contact_data else {}
        seats = json.loads(seats_json) if seats_json else {}
        trip_info = json.loads(trip_json) if trip_json else {}
        
        email = contact.get('email', '')
        phone = contact.get('phone', '')
        
        user_id = None
        for i, p in enumerate(passengers):
            data = {
                'first_name': p.get('first_name', ''),
                'last_name': p.get('last_name', ''),
                'middle_name': p.get('patronymic', ''),
                'birth_date': p.get('birth_date', ''),
                'document_type': p.get('doc_type', ''),
                'document_number': p.get('doc_number', ''),
                'citizenship': p.get('citizenship', ''),
                'phone': phone if i == 0 else None,
                'email': email if i == 0 else None
            }
            ex = get_user_by_document(p.get('doc_type', ''), p.get('doc_number', ''))
            if ex:
                if i == 0 and not user_id: user_id = ex['id']
            else:
                pid = save_passenger(data)
                if pid and i == 0 and not user_id: user_id = pid
        
        if not user_id: return "Ошибка", 500
        
        order_number = 'BRT-' + datetime.now().strftime('%Y%m%d') + '-' + str(random.randint(1000, 9999))
        total = sum(s.get('price', 0) for d in ['forward', 'backward'] for s in seats.get(d, []))
        
        # Применяем промокод
        discount_applied = 0
        applied_promo = None
        
        if promo_code:
            promo_result = check_promocode(promo_code, total)
            if promo_result['valid']:
                applied_promo = promo_code
                if promo_result['discount_percent']:
                    discount_applied = int(total * promo_result['discount_percent'] / 100)
                elif promo_result['discount_amount']:
                    discount_applied = min(promo_result['discount_amount'], total)
                
                total -= discount_applied
                apply_promocode(promo_result['promo_id'])
        
        oid = create_order(order_number=order_number, user_id=user_id, total_amount=total)
        if not oid: return "Ошибка", 500
        
        # Обновляем заказ с промокодом
        if applied_promo:
            update_order_promo(oid, applied_promo)
        
        # Бронируем места
        forward_trip_id = int(trip_info.get('forward_trip_id', 0)) if trip_info.get('forward_trip_id') and trip_info.get('forward_trip_id') != '' else 0
        backward_trip_id = int(trip_info.get('backward_trip_id', 0)) if trip_info.get('backward_trip_id') and trip_info.get('backward_trip_id') != '' else 0
        
        from utils.database.database import get_db
        
        for direction in ['forward', 'backward']:
            current_trip_id = forward_trip_id if direction == 'forward' else backward_trip_id
            if current_trip_id:
                for seat in seats.get(direction, []):
                    conn = get_db()
                    cursor = conn.cursor()
                    
                    wagon_num = str(seat.get('wagon', '1'))
                    seat_num = str(seat.get('seat', '1'))
                    
                    cursor.execute("""
                        SELECT ts.seat_id
                        FROM trip_seats ts
                        JOIN seats s ON ts.seat_id = s.id
                        JOIN wagons w ON s.wagon_id = w.id
                        WHERE ts.trip_id = ? AND w.number = ? AND s.number = ?
                    """, (current_trip_id, wagon_num, seat_num))
                    
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row:
                        reserve_seats(current_trip_id, [row['seat_id']])
        
        # Сохраняем в сессию
        session['order_number'] = order_number
        session['order_amount'] = total
        session['tickets_data'] = json.dumps({
            'order_id': oid,
            'seats': seats,
            'passengers': passengers,
            'trip_info': trip_info
        })
        session.modified = True
        
        return redirect(f'/payment/card')
    
    return render_template('confirm.html', trip_info={}, passengers=[], contact={}, seats={})


@app.route('/api/payment/cancel', methods=['POST'])
def api_payment_cancel():
    data = request.get_json()
    order_number = data.get('order_number')
    
    order = get_order_by_number(order_number)
    if not order:
        return {'success': False, 'message': 'Заказ не найден'}
    
    # Обновляем статус заказа
    update_order_status(order['id'], 'expired')
    
    # Освобождаем места
    release_expired_orders()
    
    return {'success': True, 'message': 'Бронь снята'}


@app.route('/payment/card')
def payment_card():
    order_number = session.get('order_number')
    order_amount = session.get('order_amount')
    
    if not order_number:
        return render_template('payment_card.html', order_number=None, order_amount=0)
    
    return render_template('payment_card.html', order_number=order_number, order_amount=order_amount)


@app.route('/api/payment/process', methods=['POST'])
def api_payment_process():
    import random
    
    data = request.get_json()
    order_number = data.get('order_number')
    amount = data.get('amount')
    
    order = get_order_by_number(order_number)
    if not order:
        return {'success': False, 'message': 'Заказ не найден'}
    
    update_order_status(order['id'], 'paid')
    
    save_transaction(
        order_id=order['id'],
        amount=amount,
        trans_type='payment',
        gateway='card',
        external_id='CARD-' + data.get('card_last4', '0000'),
        status='success'
    )
    
    tickets_data_str = session.get('tickets_data', '{}')
    if tickets_data_str:
        tickets_data = json.loads(tickets_data_str)
        seats = tickets_data.get('seats', {})
        passengers = tickets_data.get('passengers', [])
        trip_info = tickets_data.get('trip_info', {})
        
        fwd_id = trip_info.get('forward_trip_id', '0')
        bwd_id = trip_info.get('backward_trip_id', '0')
        forward_trip_id = int(fwd_id) if fwd_id and str(fwd_id) != '' else 0
        backward_trip_id = int(bwd_id) if bwd_id and str(bwd_id) != '' else 0
        
        p_idx = 0
        for direction in ['forward', 'backward']:
            current_trip_id = forward_trip_id if direction == 'forward' else backward_trip_id
            
            if not current_trip_id:
                continue
            
            for seat in seats.get(direction, []):
                if p_idx < len(passengers):
                    ticket_number = 'BRT-' + datetime.now().strftime('%Y%m%d') + '-' + str(random.randint(10000, 99999))
                    
                    # Сохраняем билет с seat_id=1 (заглушка)
                    from utils.database.database import get_db
                    conn = get_db()
                    cursor = conn.cursor()
                    
                    # Проверяем, есть ли хоть какой-то seat_id для этого trip
                    cursor.execute("SELECT MIN(seat_id) as sid FROM trip_seats WHERE trip_id = ?", (current_trip_id,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    seat_id = row['sid'] if row and row['sid'] else 1
                    
                    save_ticket(order['id'], {
                        'trip_id': current_trip_id,
                        'seat_id': seat_id,
                        'user_id': order['user_id'],
                        'passenger_type': 'adult',
                        'price': seat.get('price', 0),
                        'ticket_number': ticket_number
                    })
                    p_idx += 1
        
        session.pop('tickets_data', None)
    
    add_bonus_points(order['user_id'], int(amount) if amount else 0)
    update_user_loyalty(order['user_id'])
    
    session.pop('order_number', None)
    session.pop('order_amount', None)
    session.modified = True
    
    return {'success': True, 'message': 'Оплата прошла успешно'}

@app.route('/pay/<order_number>')
def pay_order(order_number):
    order = get_order_by_number(order_number)
    if not order:
        return "Заказ не найден", 404
    
    return f"""
    <html>
    <head><meta charset="UTF-8"><title>Оплата {order_number}</title>
    <style>
        body {{ font-family: Commissioner, sans-serif; text-align: center; padding-top: 100px; background: #EFF1F4; }}
        .card {{ background: #fff; border-radius: 35px; padding: 40px; max-width: 500px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
        h2 {{ color: #1E1E1E; }}
        .amount {{ font-size: 32px; font-weight: 600; color: #1E1E1E; margin: 20px 0; }}
        .status {{ color: #A3A3A3; }}
        a {{ color: #4672FF; text-decoration: none; }}
    </style></head>
    <body>
        <div class="card">
            <h2>Заказ #{order_number}</h2>
            <p class="status">Сумма к оплате</p>
            <div class="amount">{order['total_amount']} ₽</div>
            <p class="status">Статус: {order['status']}</p>
            <p class="status">Платёжный шлюз временно отключён</p>
            <p><a href="/">← Вернуться на главную</a></p>
        </div>
    </body>
    </html>
    """


@app.route('/test-db')
def test_db():
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    
    tables = ['stations', 'routes', 'trains', 'trips', 'wagons', 'seats', 'trip_seats']
    result = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        result[table] = cursor.fetchone()['cnt']
    
    conn.close()
    return result


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    user_id = login_user(email, password)
    
    if user_id:
        save_login_history(user_id, request.remote_addr, request.headers.get('User-Agent'), True)
        
        resp = make_response({'success': True, 'user_id': user_id, 'email': email})
        resp.set_cookie('brt_user_id', str(user_id), max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_user_email', email, max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_logged_in', '1', max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_saved_email', email, max_age=2592000, path='/', samesite='Lax')
        resp.set_cookie('brt_saved_password', password, max_age=2592000, path='/', samesite='Lax')
        return resp
    
    if user:
        save_login_history(user['id'], request.remote_addr, request.headers.get('User-Agent'), False)
    
    return {'success': False, 'message': 'Неверный email или пароль'}


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    
    if not email or not password:
        return {'success': False, 'message': 'Email и пароль обязательны'}
    
    user_id = register_user(email, password, first_name, last_name)
    if user_id:
        save_login_history(user_id, request.remote_addr, request.headers.get('User-Agent'), True)
        
        resp = make_response({'success': True, 'user_id': user_id, 'email': email})
        resp.set_cookie('brt_user_id', str(user_id), max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_user_email', email, max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_logged_in', '1', max_age=86400, path='/', samesite='Lax')
        resp.set_cookie('brt_saved_email', email, max_age=2592000, path='/', samesite='Lax')
        resp.set_cookie('brt_saved_password', password, max_age=2592000, path='/', samesite='Lax')
        return resp
    
    return {'success': False, 'message': 'Ошибка регистрации'}


@app.route('/api/logout', methods=['POST'])
def api_logout():
    resp = make_response({'success': True})
    resp.delete_cookie('brt_user_id', path='/')
    resp.delete_cookie('brt_user_email', path='/')
    resp.delete_cookie('brt_logged_in', path='/')
    return resp


@app.route('/api/user-status')
def api_user_status():
    user_id = request.cookies.get('brt_user_id')
    email = request.cookies.get('brt_user_email')
    logged_in = request.cookies.get('brt_logged_in')
    
    if logged_in == '1' and user_id and email:
        is_admin_user, is_super = is_admin(int(user_id))
        return {
            'logged_in': True, 
            'user_id': int(user_id), 
            'email': email,
            'is_admin': is_admin_user,
            'is_superadmin': is_super
        }
    return {'logged_in': False, 'is_admin': False}


@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/api/profile/<int:user_id>')
def api_profile(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return {'error': 'Пользователь не найден'}, 404
    
    result = {}
    for key in ['id', 'email', 'phone', 'first_name', 'last_name', 'middle_name', 
                'birth_date', 'gender', 'citizenship', 'bonus_points', 'loyalty_level',
                'document_type', 'document_number']:
        if user.get(key):
            result[key] = user[key]
    
    return result
    

@app.route('/api/profile/update', methods=['POST'])
def api_profile_update():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return {'success': False, 'message': 'Не авторизован'}
    
    data = request.get_json()
    
    if update_profile(int(user_id), data):
        return {'success': True, 'message': 'Данные сохранены'}
    return {'success': False, 'message': 'Ошибка сохранения'}


@app.route('/api/profile/change-password', methods=['POST'])
def api_profile_change_password():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return {'success': False, 'message': 'Не авторизован'}
    
    data = request.get_json()
    success, message = change_password(
        int(user_id),
        data.get('current_password', ''),
        data.get('new_password', '')
    )
    return {'success': success, 'message': message}


@app.route('/api/profile/tickets')
def api_profile_tickets():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return []
    return get_user_tickets(int(user_id))


@app.route('/api/profile/login-history')
def api_profile_login_history():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return []
    return get_user_login_history(int(user_id))


@app.route('/api/profile/bonus')
def api_profile_bonus():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return {'points': 0, 'level': 'none', 'total_spent': 0}
    
    user_id = int(user_id)
    bonus = get_user_bonus(user_id)  # берёт loyalty_level из БД
    total_spent = get_user_total_spent(user_id)
    
    # Пересчитываем уровень на основе потраченной суммы
    level = calculate_loyalty_level(total_spent)
    
    # Если уровень из БД отличается — обновляем БД
    if bonus.get('level') != level:
        update_user_loyalty(user_id)
    
    return {
        'points': bonus.get('points', 0),
        'level': level, 
        'total_spent': total_spent
    }


@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/api/admin/check')
def api_admin_check():
    user_id = request.cookies.get('brt_user_id')
    if not user_id:
        return {'is_admin': False}
    
    is_admin_user, is_super = is_admin(int(user_id))
    return {'is_admin': is_admin_user, 'is_superadmin': is_super}

@app.route('/api/admin/promocodes')
def api_admin_promocodes():
    return get_all_promocodes()

@app.route('/api/admin/promocodes/create', methods=['POST'])
def api_admin_create_promocode():
    data = request.get_json()
    code = data.get('code')
    if not code:
        return {'success': False, 'message': 'Введите код'}
    
    promo_id = create_promocode(
        code=code,
        discount_percent=int(data.get('discount_percent', 0) or 0),
        discount_amount=int(data.get('discount_amount', 0) or 0),
        min_order=int(data.get('min_order_amount', 0) or 0),
        max_uses=int(data.get('max_uses', 0) or 0),
        expires_at=data.get('expires_at') or None
    )
    
    if promo_id:
        admin_id = request.cookies.get('brt_user_id', 0)
        save_admin_action(int(admin_id), 'create_promo', f'Создан промокод {code}', request.remote_addr)
        return {'success': True}
    return {'success': False, 'message': 'Ошибка создания'}

@app.route('/api/admin/promocodes/delete', methods=['POST'])
def api_admin_delete_promocode():
    data = request.get_json()
    promo_id = data.get('id', 0)
    result = delete_promocode(promo_id)
    if result:
        save_admin_action(int(request.cookies.get('brt_user_id', 0)), 'delete_promo', f'Удалён промокод #{promo_id}', request.remote_addr)
    return {'success': result}

@app.route('/api/promo/check', methods=['POST'])
def api_promo_check():
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    order_amount = data.get('order_amount', 0)
    return check_promocode(code, order_amount)

@app.route('/api/admin/logs')
def api_admin_logs():
    return get_admin_actions()

@app.route('/api/admin/logs/clear', methods=['POST'])
def api_admin_clear_logs():
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM admin_actions")
        conn.commit()
        return {'success': True, 'message': 'Логи очищены'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/users/update', methods=['POST'])
def api_admin_update_user():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return {'success': False, 'message': 'user_id не указан'}
    
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        fields = []
        values = []
        
        # Разрешенные для обновления поля
        allowed_fields = [
            'email', 'phone', 'first_name', 'last_name', 'middle_name',
            'birth_date', 'document_type', 'document_number', 
            'bonus_points', 'loyalty_level', 'language', 'currency'
        ]
        
        for field in allowed_fields:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return {'success': False, 'message': 'Нет полей для обновления'}
        
        # Добавляем обновление времени
        fields.append("updated_at = datetime('now')")
        values.append(user_id)
        
        query = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        
        # Логируем действие
        admin_id = request.cookies.get('brt_user_id', 0)
        changes = ', '.join(allowed_fields)
        save_admin_action(
            int(admin_id), 
            'edit_user', 
            f'Пользователь #{user_id} обновлён. Поля: {changes}', 
            request.remote_addr
        )
        
        return {'success': True, 'message': 'Данные сохранены'}
        
    except Exception as e:
        print(f"Ошибка обновления пользователя: {e}")
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/users/delete', methods=['POST'])
def api_admin_delete_user():
    data = request.get_json()
    user_id = data.get('user_id')
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        save_admin_action(int(request.cookies.get('brt_user_id', 0)), 'delete_user', f'User {user_id} deleted', request.remote_addr)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/admins/add', methods=['POST'])
def api_admin_add_admin():
    data = request.get_json()
    user_id = data.get('user_id')
    
    # Получаем email пользователя
    user = get_user_by_id(user_id)
    email = user['email'] if user else f'User {user_id}'
    
    result = add_admin(user_id, data.get('permissions', '["all"]'), data.get('is_superadmin', 0))
    if result:
        admin_id = request.cookies.get('brt_user_id', 0)
        role = 'супер-админом' if data.get('is_superadmin') else 'админом'
        save_admin_action(
            int(admin_id), 
            'add_admin', 
            f'Добавлен {"супер-админ" if data.get("is_superadmin") else "админ"} {email}', 
            request.remote_addr
        )
    return {'success': result}


@app.route('/api/admin/admins/remove', methods=['POST'])
def api_admin_remove_admin():
    data = request.get_json()
    user_id = data.get('user_id')
    
    # Получаем email пользователя
    user = get_user_by_id(user_id)
    email = user['email'] if user else f'User {user_id}'
    
    result = remove_admin(user_id)
    if result:
        admin_id = request.cookies.get('brt_user_id', 0)
        save_admin_action(
            int(admin_id), 
            'remove_admin', 
            f'Удалён админ {email}', 
            request.remote_addr
        )
    return {'success': result}

@app.route('/api/admin/reports/sales')
def api_admin_sales_report():
    start = request.args.get('start')
    end = request.args.get('end')
    return get_sales_report(start, end)

@app.route('/api/admin/dashboard')
def api_admin_dashboard():
    return get_dashboard_stats()

@app.route('/api/admin/orders')
def api_admin_orders():
    return get_all_orders()

@app.route('/api/admin/users')
def api_admin_users():
    return get_all_users()

@app.route('/api/admin/trains')
def api_admin_trains():
    return get_all_trains()

@app.route('/api/admin/trips/all')
def admin_trips_all():
    """Получить все рейсы с информацией о вагонах и местах."""
    trips = get_all_trips_with_details(limit=100)
    return jsonify(trips)

@app.route('/api/admin/stations')
def api_admin_stations():
    return get_all_stations()

@app.route('/api/admin/tickets')
def api_admin_tickets():
    return get_all_tickets()

@app.route('/api/admin/reports/tickets-by-date')
def api_admin_tickets_by_date():
    date = request.args.get('date')
    return get_tickets_by_date(date)

@app.route('/api/admin/admins')
def api_admin_admins():
    admins = get_all_admins()
    for admin in admins:
        if 'id' not in admin:
            admin['id'] = admin.get('user_id')
    return admins

@app.route('/api/admin/settings', methods=['POST'])
def api_admin_settings():
    data = request.get_json()
    fee = data.get('service_fee', 200)
    save_admin_action(int(request.cookies.get('brt_user_id', 0)), 'update_settings', f'Service fee changed to {fee}', request.remote_addr)
    return {'success': True, 'message': 'Сохранено'}

@app.route('/api/admin/users/get')
def api_admin_get_user():
    """Получить полные данные пользователя для редактирования."""
    user_id = request.args.get('user_id')
    if not user_id:
        return {'error': 'user_id не указан'}, 400
    
    user = get_user_by_id(int(user_id))
    if not user:
        return {'error': 'Пользователь не найден'}, 404
    
    # Исключаем чувствительные поля
    safe_fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'middle_name', 
                   'birth_date', 'document_type', 'document_number', 'bonus_points',
                   'loyalty_level', 'language', 'currency', 'updated_at']
    
    result = {k: user[k] for k in safe_fields if k in user}
    return result

@app.route('/api/admin/users/create', methods=['POST'])
def api_admin_create_user():
    """Создание пользователя админом без входа в его аккаунт."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    
    if not email or not password:
        return {'success': False, 'message': 'Email и пароль обязательны'}
    
    # Проверяем, существует ли уже пользователь
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        return {'success': True, 'user_id': existing['id'], 'message': 'Пользователь уже существует'}
    
    # Создаём пользователя
    user_id = register_user(email, password, first_name)
    if user_id:
        admin_id = request.cookies.get('brt_user_id', 0)
        save_admin_action(int(admin_id), 'create_user', f'Создан пользователь {email}', request.remote_addr)
        return {'success': True, 'user_id': user_id}
    
    return {'success': False, 'message': 'Ошибка создания пользователя'}


@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    data = request.get_json()
    name = data.get('name', '')
    email = data.get('email', '')
    message = data.get('message', '')
    
    # Здесь можно сохранить в БД или отправить на почту
    print(f"Feedback: {name} ({email}): {message}")
    
    return {'success': True, 'message': 'Сообщение отправлено'}


@app.route('/info/<page>')
def info_page(page):
    """Универсальный маршрут для информационных страниц"""
    valid_pages = ['contacts', 'cookies', 'privacy', 'advertisers', 'bloggers', 
                   'about', 'career', 'reviews']
    
    if page not in valid_pages:
        abort(404)
    
    # Данные для каждой страницы
    page_data = {
        'contacts': {
            'title': 'Контакты'
        },
        'cookies': {
            'title': 'Использование cookie'
        },
        'privacy': {
            'title': 'Конфиденциальность'
        },
        'advertisers': {
            'title': 'Рекламодателям'
        },
        'bloggers': {
            'title': 'Блогерам'
        },
        'about': {
            'title': 'О компании'
        },
        'career': {
            'title': 'Карьера'
        },
        'reviews': {
            'title': 'Отзывы'
        }
    }
    
    return render_template(f'info/{page}.html', 
                         page=page, 
                         data=page_data[page])


@app.route('/api/ticket/<ticket_number>/pdf')
def download_ticket_pdf(ticket_number):
    from urllib.parse import quote
    
    ticket = get_ticket_by_number(ticket_number)
    if not ticket:
        return "Билет не найден", 404
    
    ticket = dict(ticket)
    
    dep_dt = str(ticket.get('departure_datetime', ''))
    arr_dt = str(ticket.get('arrival_datetime', ''))
    dep_date = dep_time = arr_date = arr_time = ''
    if dep_dt:
        parts = dep_dt.split(' ')
        dep_date = parts[0] if len(parts) > 0 else ''
        dep_time = parts[1][:5] if len(parts) > 1 else ''
    if arr_dt:
        parts = arr_dt.split(' ')
        arr_date = parts[0] if len(parts) > 0 else ''
        arr_time = parts[1][:5] if len(parts) > 1 else ''
    
    passenger_name = f"{ticket.get('last_name', '')} {ticket.get('first_name', '')} {ticket.get('middle_name', '')}".strip()
    
    html_content = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Билет {ticket_number}</title><style>@page{{size:A4;margin:10mm}}*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Arial,sans-serif;padding:20px}}.ticket{{border:2px solid #4672FF;border-radius:20px;padding:30px;max-width:800px;margin:0 auto}}.ticket__header{{text-align:center;border-bottom:2px solid #E4E5E8;padding-bottom:20px;margin-bottom:20px}}.ticket__logo{{font-size:28px;font-weight:700;color:#4672FF}}.ticket__number{{font-size:14px;color:#999;margin-top:5px}}.ticket__route{{text-align:center;margin:20px 0;font-size:24px;font-weight:600;color:#1E1E1E}}.ticket__info{{width:100%;border-collapse:collapse;margin:20px 0}}.ticket__info td{{padding:10px;border-bottom:1px solid #eee;vertical-align:top}}.ticket__info-label{{font-size:12px;color:#999}}.ticket__info-value{{font-size:16px;font-weight:500;color:#1E1E1E}}.ticket__passenger{{background:#F5F5F7;border-radius:12px;padding:15px;margin:15px 0}}.ticket__footer{{text-align:center;margin-top:20px;padding-top:20px;border-top:2px solid #eee;font-size:12px;color:#999}}@media print{{body{{padding:0}}}}</style></head><body><div class="ticket"><div class="ticket__header"><div class="ticket__logo">BRT</div><div class="ticket__number">Билет № {ticket_number}</div></div><div class="ticket__route">{ticket.get('from_city', '—')} → {ticket.get('to_city', '—')}</div><table class="ticket__info"><tr><td><span class="ticket__info-label">Поезд</span><br><span class="ticket__info-value">{ticket.get('train_number', '—')} {ticket.get('train_name', '')}</span></td><td><span class="ticket__info-label">Вагон / Место</span><br><span class="ticket__info-value">{ticket.get('wagon_number', '—')} / {ticket.get('seat_number', '—')}</span></td></tr><tr><td><span class="ticket__info-label">Отправление</span><br><span class="ticket__info-value">{dep_date} в {dep_time}</span></td><td><span class="ticket__info-label">Прибытие</span><br><span class="ticket__info-value">{arr_date} в {arr_time}</span></td></tr><tr><td><span class="ticket__info-label">Станция отправления</span><br><span class="ticket__info-value">{ticket.get('from_station', ticket.get('from_city', '—'))}</span></td><td><span class="ticket__info-label">Станция прибытия</span><br><span class="ticket__info-value">{ticket.get('to_station', ticket.get('to_city', '—'))}</span></td></tr><tr><td><span class="ticket__info-label">Тип вагона</span><br><span class="ticket__info-value">{ticket.get('wagon_type', '—')}</span></td><td><span class="ticket__info-label">Цена</span><br><span class="ticket__info-value">{ticket.get('price', 0)} ₽</span></td></tr></table><div class="ticket__passenger"><span class="ticket__info-label">Пассажир</span><br><span class="ticket__info-value">{passenger_name or '—'}</span></div><div class="ticket__footer"><p>BRT — Bahn Routing Tools</p><p>Счастливого пути!</p></div></div></body></html>"""
    
    response = make_response(html_content)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    
    # Кодируем имя файла для избежания ошибки latin-1
    filename = f'Билет_{ticket_number}.html'
    encoded_filename = quote(filename)
    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
    
    return response


@app.route('/api/tickets-by-order/<order_number>')
def api_tickets_by_order(order_number):
    tickets = get_tickets_by_order_number(order_number)
    return jsonify(tickets)

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email or '@' not in email or '.' not in email:
            return jsonify({'success': False, 'message': 'Введите корректный email'}), 400
        
        from utils.database.database import subscribe_email
        result = subscribe_email(email)
        
        if result:
            return jsonify({'success': True, 'message': 'Спасибо за подписку!'})
        else:
            return jsonify({'success': False, 'message': 'Ошибка сохранения'}), 500
            
    except Exception as e:
        print(f"API Error (subscribe): {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500


if __name__ == '__main__':
    app.run(debug=True)