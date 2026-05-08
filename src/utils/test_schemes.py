#!/usr/bin/env python3
"""
Тест доступности схем вагонов через API РЖД.
Проверяет все возможные способы получить scheme_html/scheme_image.
"""

import json
import requests
from datetime import datetime, timedelta
from rzd_api import RzdClient, Config, Api


def test_schemes():
    """Проверяет все способы получить схемы вагонов."""
    
    client = RzdClient(Config(language='ru', timeout=30.0))
    raw_api = Api(Config(language='ru', timeout=30.0))
    
    # Тестовые станции
    from_station = "Москва"
    to_station = "Санкт-Петербург"
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print("=" * 70)
    print(f"ТЕСТ СХЕМ ВАГОНОВ: {from_station} → {to_station}, {tomorrow}")
    print("=" * 70)
    
    # 1. Получаем список поездов
    print("\n1. Получаем список поездов...")
    try:
        tickets = client.search_tickets(
            from_station=from_station,
            to_station=to_station,
            departure_date=tomorrow
        )
        
        if isinstance(tickets, list):
            trains = tickets
        elif isinstance(tickets, dict):
            trains = tickets.get('forward', tickets.get('trains', []))
        else:
            trains = []
        
        print(f"   Найдено поездов: {len(trains)}")
        
        if not trains:
            print("   Поезда не найдены, тест остановлен.")
            return
        
        # Берём первые 3 поезда
        test_trains = trains[:3]
        
    except Exception as e:
        print(f"   Ошибка: {e}")
        return
    
    # 2. Проверяем CarGroups в ответе поиска
    print("\n2. Проверяем CarGroups в ответе поиска...")
    for i, train in enumerate(test_trains):
        car_groups = train.get('CarGroups', [])
        print(f"\n   Поезд {i+1}: {train.get('TrainNumber', '?')} {train.get('DisplayTrainNumber', '')}")
        print(f"   CarGroups: {len(car_groups)}")
        
        for j, group in enumerate(car_groups[:3]):
            group_cars = group.get('Cars', [])
            print(f"     Группа {j+1}: {group.get('ServiceClassName', '?')} — вагонов: {len(group_cars)}")
            
            for k, car in enumerate(group_cars[:2]):
                car_keys = list(car.keys())
                has_schemes = 'schemes' in car or 'Schemes' in car
                has_type = car.get('CarTypeName', car.get('typeLoc', '?'))
                has_seats = car.get('TotalPlaceQuantity', car.get('PlaceQuantity', '?'))
                
                print(f"       Вагон {k+1}: тип={has_type}, мест={has_seats}, schemes={'✅' if has_schemes else '❌'}")
                
                if has_schemes:
                    schemes = car.get('schemes', car.get('Schemes', {}))
                    print(f"         scheme_html: {'✅' if schemes.get('html') else '❌'}")
                    print(f"         scheme_image: {'✅' if schemes.get('image') else '❌'}")
                    if schemes.get('html'):
                        html_content = schemes['html']
                        preview = (html_content if isinstance(html_content, str) else ''.join(html_content))[:200]
                        print(f"         HTML preview: {preview}...")
    
    # 3. Пробуем train_carriages для первого поезда
    if test_trains:
        print("\n3. Пробуем train_carriages...")
        first_train = test_trains[0]
        train_number = first_train.get('TrainNumber') or first_train.get('DisplayTrainNumber', '')
        dep_time = (first_train.get('LocalDepartureDateTime') or first_train.get('DepartureDateTime', ''))
        
        if dep_time and len(dep_time) >= 16:
            dep_date = dep_time[:10]
            dep_time_short = dep_time[11:16]
            
            try:
                code0 = client.resolve_station_code(from_station)
                code1 = client.resolve_station_code(to_station)
                
                print(f"   Запрос: поезд {train_number}, {dep_date} {dep_time_short}")
                print(f"   Коды станций: {code0} → {code1}")
                
                # Способ 1: через RzdClient
                print("\n   Способ 1: client.get_carriages()")
                try:
                    cars_data = client.get_carriages(
                        from_station=from_station,
                        to_station=to_station,
                        departure_date=dep_date,
                        departure_time=dep_time_short,
                        train_number=train_number
                    )
                    print(f"   ✅ Успех! Ключи: {list(cars_data.keys())}")
                    cars = cars_data.get('cars', cars_data.get('Cars', []))
                    if cars:
                        car = cars[0]
                        schemes = car.get('schemes', {})
                        print(f"   schemes.html: {'✅' if schemes.get('html') else '❌'}")
                        print(f"   schemes.image: {'✅' if schemes.get('image') else '❌'}")
                except Exception as e:
                    print(f"   ❌ Ошибка: {str(e)[:200]}")
                
                # Способ 2: через raw API (POST)
                print("\n   Способ 2: raw_api.train_carriages_data()")
                try:
                    cars_data = raw_api.train_carriages_data({
                        'OriginCode': code0,
                        'DestinationCode': code1,
                        'DepartureDate': f"{dep_date}T{dep_time_short}:00",
                        'TrainNumber': train_number,
                        'CarNumber': '01',
                        'Provider': 'P1',
                    })
                    print(f"   ✅ Успех! Ключи: {list(cars_data.keys())}")
                    cars = cars_data.get('cars', [])
                    if cars:
                        car = cars[0]
                        schemes = car.get('schemes', {})
                        print(f"   schemes.html: {'✅' if schemes.get('html') else '❌'}")
                        print(f"   schemes.image: {'✅' if schemes.get('image') else '❌'}")
                except Exception as e:
                    print(f"   ❌ Ошибка: {str(e)[:200]}")
                
                # Способ 3: прямой HTTP-запрос
                print("\n   Способ 3: прямой POST-запрос к API")
                try:
                    session = requests.Session()
                    session.headers.update({
                        'Accept': 'application/json',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': 'https://ticket.rzd.ru/',
                    })
                    
                    response = session.post(
                        'https://ticket.rzd.ru/api/v1/railway/car/place/prices',
                        params={'service_provider': 'B2B_RZD'},
                        json={
                            'OriginCode': code0,
                            'DestinationCode': code1,
                            'DepartureDate': f"{dep_date}T{dep_time_short}:00",
                            'TrainNumber': train_number,
                            'CarNumber': '01',
                            'Provider': 'P1',
                            'SpecialPlacesDemand': 'StandardPlacesAndForDisabledPersons',
                            'TariffType': 'Single',
                        },
                        timeout=30
                    )
                    print(f"   Статус: {response.status_code}")
                    if response.status_code == 200:
                        data = response.json()
                        print(f"   ✅ Успех! Ключи: {list(data.keys())}")
                        cars = data.get('cars', data.get('Cars', []))
                        if cars:
                            car = cars[0]
                            schemes = car.get('schemes', {})
                            print(f"   schemes.html: {'✅' if schemes.get('html') else '❌'}")
                            print(f"   schemes.image: {'✅' if schemes.get('image') else '❌'}")
                    else:
                        print(f"   Ответ: {response.text[:300]}")
                except Exception as e:
                    print(f"   ❌ Ошибка: {str(e)[:200]}")
                    
            except Exception as e:
                print(f"   Ошибка получения кодов станций: {e}")
    
    print("\n" + "=" * 70)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)


if __name__ == '__main__':
    test_schemes()