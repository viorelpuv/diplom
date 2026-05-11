# app.py — полный код
from flask import Flask, render_template, request, redirect
from datetime import datetime, date
from utils.rail_api import RZDApi
from utils.currency import format_price
from flask_babel import Babel, _
from utils.payment import create_payment_for_order

from utils.database.database import (
    init_db, save_passenger, create_order, save_ticket, 
    save_transaction, update_order_status, save_train_full, 
    get_order_by_number, get_user_by_document
)

app = Flask(__name__)

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
        'id': trip.get('trip_id', abs(hash(f"{trip.get('train_number')}_{dep_dt}"))),
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


@app.route('/')
def main():
    return render_template('index.html')


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
                results.append(formatted)
                print(f"  📝 Вызов save_train_full для {formatted.get('train_number')}")
                result = save_train_full(formatted, from_city, to_city)
                print(f"  📝 Результат: {result}")
        
        return_results = []
        for train in backward_trains:
            formatted = format_train(train, to_city, from_city, total_passengers)
            if formatted:
                formatted['from_station'], formatted['to_station'] = formatted['to_station'], formatted['from_station']
                return_results.append(formatted)
                try:
                    save_train_full(formatted, to_city, from_city)
                except Exception as e:
                    print(f"  ⚠️ Ошибка сохранения: {e}")
        
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
                results.append(formatted)
                try:
                    save_train_full(formatted, from_city, to_city)
                except:
                    pass

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
    return {'RUB': 1, 'USD': get_rate('USD'), 'EUR': get_rate('EUR')}


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
        
        passengers = json.loads(passengers_data) if passengers_data else []
        contact = json.loads(contact_data) if contact_data else {}
        seats = json.loads(seats_json) if seats_json else {}
        trip_info = json.loads(trip_json) if trip_json else {}
        
        # Сохраняем в БД
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
        oid = create_order(order_number=order_number, user_id=user_id, total_amount=total)
        if not oid: return "Ошибка", 500
        update_order_status(oid, 'pending')
        
        return redirect(f'/pay/{order_number}')
    
    return render_template('confirm.html', trip_info={}, passengers=[], contact={}, seats={})


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


if __name__ == '__main__':
    app.run(debug=True)

    
@app.route('/test-db')
def test_db():
    from utils.database.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    
    # Считаем записи во всех таблицах
    tables = ['stations', 'routes', 'trains', 'trips', 'wagons', 'seats', 'trip_seats']
    result = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        result[table] = cursor.fetchone()['cnt']
    
    conn.close()
    return result
    