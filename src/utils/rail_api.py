# rzd_api.py
import sys
from datetime import date, datetime
from typing import Optional, List, Dict, Union
from rzd_api import RzdClient, Config


class RZDApi:
    """
    API клиент для работы с РЖД через библиотеку rzd-api.
    Документация: https://pypi.org/project/rzd-api/
    GitHub: https://github.com/drGOD/rzd-api
    """
    
    def __init__(self, test_mode: bool = False):
        config = Config(
            language='ru',
            timeout=30.0
        )
        self.client = RzdClient(config=config)
        self.test_mode = test_mode
    
    # ============================================
    # СТАНЦИИ
    # ============================================
    
    def search_stations(self, query: str) -> List[Dict]:
        """Поиск станций по названию. Возвращает список словарей."""
        stations = self.client.find_stations(query, transport_type='rail', group_results=True)
        
        result = []
        for station_group in stations:
            group_name = station_group.get('name', '')
            for station in station_group.get('stations', []):
                result.append({
                    "code": station.get('code', ''),
                    "name": station.get('name', ''),
                    "region": group_name
                })
        return result
    
    def resolve_station_code(self, station: str) -> str:
        """Получение кода станции по названию или возврат кода если уже передан."""
        return self.client.resolve_station_code(station)
    
    # ============================================
    # ПОИСК РЕЙСОВ
    # ============================================
    
    def search_tickets(
        self,
        from_station: Union[str, int],
        to_station: Union[str, int],
        departure_date: Union[str, date, datetime],
        return_date: Optional[Union[str, date, datetime]] = None,
        only_with_seats: bool = True,
        include_transfers: bool = False,
        transport_type: str = 'trains'
    ) -> Dict:
        """
        Поиск билетов. Если указан return_date — возвращает словарь с ключами 'forward' и 'back'.
        
        Args:
            from_station: Код или название станции отправления
            to_station: Код или название станции прибытия
            departure_date: Дата отправления (str, date или datetime)
            return_date: Дата возврата (опционально)
            only_with_seats: Только поезда с доступными местами
            include_transfers: Включая маршруты с пересадками
            transport_type: 'trains', 'suburban', 'all'
        """
        return self.client.search_tickets(
            from_station=from_station,
            to_station=to_station,
            departure_date=departure_date,
            return_date=return_date,
            only_with_seats=only_with_seats,
            include_transfers=include_transfers,
            transport_type=transport_type
        )
    
    def format_trip_for_card(self, trip: Dict) -> Dict:
        dep_time = trip.get('LocalDepartureDateTime') or trip.get('DepartureDateTime', '')
        arr_time = trip.get('LocalArrivalDateTime') or trip.get('ArrivalDateTime', '')
        
        duration = trip.get('Duration', 0)
        if not duration and dep_time and arr_time:
            try:
                dep_dt = datetime.fromisoformat(dep_time)
                arr_dt = datetime.fromisoformat(arr_time)
                duration = int((arr_dt - dep_dt).total_seconds() // 60)
            except:
                pass
        
        prices = []
        car_groups = trip.get('CarGroups', [])
        
        for group in car_groups:
            for key in ['MinPrice', 'Price', 'Tariff']:
                val = group.get(key, 0)
                if val and val > 0:
                    prices.append(val)
            
            group_cars = group.get('Cars', [])
            for car in group_cars:
                for key in ['Price', 'Tariff', 'MinPrice']:
                    val = car.get(key, 0)
                    if val and val > 0:
                        prices.append(val)
        
        for key in ['MinPrice', 'minPrice', 'Price', 'price', 'TotalPrice']:
            val = trip.get(key, 0)
            if val and val > 0:
                prices.append(val)
        
        cars = trip.get('Cars', [])
        for car in cars:
            for key in ['Price', 'price', 'TotalPrice', 'MinPrice', 'Tariff']:
                val = car.get(key, 0)
                if val and val > 0:
                    prices.append(val)
        
        min_price = min(prices) if prices else 0
        
        # Собираем все вагоны
        all_cars = []
        for group in car_groups:
            group_cars = group.get('Cars', [])
            all_cars.extend(group_cars)
        if not all_cars:
            all_cars = cars
        
        # Ищем schemes в CarGroups
        schemes = None
        for group in car_groups:
            group_cars = group.get('Cars', [])
            for car in group_cars:
                car_schemes = car.get('schemes', car.get('Schemes'))
                if car_schemes and (car_schemes.get('html') or car_schemes.get('image')):
                    schemes = car_schemes
                    print(f"[DEBUG] Найдены schemes в вагоне!")
                    break
            if schemes:
                break
        
        if not schemes:
            print(f"[DEBUG] Schemes не найдены в CarGroups")
        
        return {
            "trip_id": trip.get('ObjectId', trip.get('Id', '')),
            "train_number": trip.get('TrainNumber') or trip.get('DisplayTrainNumber', ''),
            "train_name": trip.get('TrainName', '') or trip.get('Brand', '') or ', '.join(trip.get('CarrierDisplayNames', [])),
            "departure_time": dep_time[11:16] if len(dep_time) >= 16 else dep_time,
            "arrival_time": arr_time[11:16] if len(arr_time) >= 16 else arr_time,
            "departure_date": dep_time[:10] if len(dep_time) >= 10 else dep_time,
            "arrival_date": arr_time[:10] if len(arr_time) >= 10 else arr_time,
            "departure_datetime": dep_time,
            "arrival_datetime": arr_time,
            "from_station": trip.get('OriginStationName', ''),
            "to_station": trip.get('DestinationStationName', ''),
            "from_station_code": trip.get('OriginStationCode', ''),
            "to_station_code": trip.get('DestinationStationCode', ''),
            "duration_minutes": duration,
            "min_price": min_price,
            "has_transfer": trip.get('HasTransfer', False) or len(trip.get('Transfers', [])) > 0,
            "cars": all_cars,
            "schemes": schemes,
        }
    
    # ============================================
    # ВАГОНЫ И МЕСТА
    # ============================================
    
    def get_carriages(
        self,
        from_station: Union[str, int],
        to_station: Union[str, int],
        departure_date: Union[str, date, datetime],
        departure_time: str,
        train_number: str,
        car_number: str = '01'
    ) -> Dict:
        """
        Получение информации о вагонах и свободных местах.
        
        Args:
            from_station: Станция отправления
            to_station: Станция прибытия
            departure_date: Дата отправления
            departure_time: Время отправления (HH:MM)
            train_number: Номер поезда
            car_number: Номер вагона
        """
        return self.client.get_carriages(
            from_station=from_station,
            to_station=to_station,
            departure_date=departure_date,
            departure_time=departure_time,
            train_number=train_number,
            car_number=car_number
        )
    
    def format_wagon_for_card(self, wagon: Dict) -> Dict:
        """Форматирует данные вагона для отображения в карточке."""
        seat_info = wagon.get('Seats', {})
        return {
            "wagon_id": wagon.get('CarNumber', ''),
            "wagon_type": wagon.get('CarTypeName', ''),
            "class": wagon.get('ServiceClassName', '').lower(),
            "seats_bottom": seat_info.get('Bottom', 0),
            "seats_top": seat_info.get('Top', 0),
            "seats_bottom_side": seat_info.get('BottomSide', 0),
            "seats_top_side": seat_info.get('TopSide', 0),
            "seats_single": seat_info.get('Single', 0),
            "total_available": sum(seat_info.values()) if seat_info else 0,
            "price": wagon.get('Price', 0),
            "service_fee": wagon.get('ServiceFee', 0)
        }
    
    # ============================================
    # СТАНЦИИ НА МАРШРУТЕ
    # ============================================
    
    def get_route_stations(self, object_id: str) -> List[Dict]:
        """Список станций по маршруту следования поезда."""
        stations = self.client.get_route_stations(object_id)
        return [
            {
                "station_name": s.get('StationName', ''),
                "station_code": s.get('StationCode', ''),
                "arrival_time": s.get('ArrivalTime', ''),
                "departure_time": s.get('DepartureTime', ''),
                "stop_duration": s.get('StopDuration', 0)
            }
            for s in stations
        ]
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def get_available_wagons_summary(self, trip: Dict) -> List[Dict]:
        """
        Получает сводку по доступным вагонам для рейса.
        Группирует по типу вагона и классу.
        """
        cars = trip.get('Cars', [])
        summary = {}
        
        for car in cars:
            car_type = car.get('CarTypeName', '')
            class_name = car.get('ServiceClassName', '')
            key = f"{car_type} / {class_name}"
            
            if key not in summary:
                summary[key] = {
                    "type_name": car_type,
                    "class_name": class_name,
                    "min_price": car.get('Price', 0),
                    "total_seats": 0,
                    "seats_bottom": 0,
                    "seats_top": 0
                }
            
            seats = car.get('Seats', {})
            summary[key]["min_price"] = min(summary[key]["min_price"], car.get('Price', 0))
            summary[key]["total_seats"] += sum(seats.values())
            summary[key]["seats_bottom"] += seats.get('Bottom', 0)
            summary[key]["seats_top"] += seats.get('Top', 0)
        
        return list(summary.values())
    
    def format_datetime_ru(self, datetime_str: str) -> str:
        """Форматирует дату в русский формат (например, '19 янв')."""
        if not datetime_str:
            return ''
        try:
            dt = datetime.fromisoformat(datetime_str)
            months_ru = [
                '', 'янв', 'фев', 'мар', 'апр', 'мая', 'июн',
                'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'
            ]
            return f"{dt.day} {months_ru[dt.month]}"
        except (ValueError, IndexError):
            return datetime_str
    
    def format_duration(self, minutes: int) -> str:
        """Форматирует длительность в читаемый вид."""
        if not minutes:
            return '0 мин'
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours} ч {mins:02d} мин"
        return f"{mins} мин"
    
    def format_seats_text(self, wagon: Dict) -> str:
        """Форматирует информацию о местах в читаемый вид."""
        parts = []
        if wagon.get('seats_bottom'):
            parts.append(f"{wagon['seats_bottom']} ниж")
        if wagon.get('seats_top'):
            parts.append(f"{wagon['seats_top']} верх")
        if wagon.get('seats_bottom_side'):
            parts.append(f"{wagon['seats_bottom_side']} ниж.бок")
        if wagon.get('seats_top_side'):
            parts.append(f"{wagon['seats_top_side']} верх.бок")
        if wagon.get('seats_single'):
            parts.append(f"{wagon['seats_single']} мест")
        return ', '.join(parts) if parts else 'нет мест'

    

################################################################



class RZDCli:
    """Консольный интерфейс для работы с API РЖД."""
    
    def __init__(self):
        self.api = RZDApi()
        self.commands = {
            'stations': self.cmd_stations,
            'trips': self.cmd_trips,
            'cars': self.cmd_cars,
            'route': self.cmd_route,
            'help': self.cmd_help,
            'exit': self.cmd_exit,
            'q': self.cmd_exit,
        }
    
    def run(self):
        """Запуск интерактивного режима."""
        print("=" * 60)
        print("  RZD API — Консольный клиент для поиска ж/д билетов")
        print("=" * 60)
        print("  Введите 'help' для списка команд, 'exit' для выхода\n")
        
        while True:
            try:
                cmd_input = input("rzd> ").strip()
                if not cmd_input:
                    continue
                
                parts = cmd_input.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    print(f"Неизвестная команда: {cmd}. Введите 'help' для списка команд.")
            except KeyboardInterrupt:
                print("\nДо свидания!")
                break
            except Exception as e:
                print(f"Ошибка: {e}")
    
    def cmd_help(self, args):
        """Показать справку."""
        print("""
Доступные команды:
──────────────────────────────────────────────────────────
  stations <запрос>    Поиск станций по названию
                       Пример: stations Москва
  
  trips <откуда> <куда> [дата]
                       Поиск рейсов между станциями
                       Пример: trips Москва Питер
                       Пример: trips Москва Питер 2026-05-01
  
  cars <откуда> <куда> <дата> <время> <номер поезда>
                       Информация о вагонах и местах
                       Пример: cars Москва Питер 2026-05-01 06:30 001А
  
  route <id рейса>    Станции на маршруте
                       Пример: route ABC123
  
  help                 Эта справка
  exit, q              Выход
──────────────────────────────────────────────────────────
        """)
    
    def cmd_stations(self, args):
        """Поиск станций."""
        if not args:
            print("Укажите название станции. Пример: stations Москва")
            return
        
        print(f"Поиск станций: '{args}'...")
        stations = self.api.search_stations(args)
        
        if not stations:
            print("Ничего не найдено.")
            return
        
        print(f"\nНайдено {len(stations)} станций:\n")
        print(f"{'Код':<12} {'Название':<40} {'Регион':<20}")
        print("-" * 72)
        for s in stations[:20]:
            print(f"{s['code']:<12} {s['name']:<40} {s['region']:<20}")
    
    def cmd_trips(self, args):
        """Поиск рейсов."""
        if not args:
            print("Укажите станции и дату. Пример: trips Москва Питер 2026-05-01")
            return
        
        parts = args.split()
        if len(parts) < 2:
            print("Нужно минимум 2 параметра: откуда и куда. Дата опциональна.")
            return
        
        from_station = parts[0]
        to_station = parts[1]
        departure_date = parts[2] if len(parts) > 2 else date.today().strftime('%Y-%m-%d')
        
        print(f"\nПоиск рейсов: {from_station} → {to_station}, {departure_date}")
        print("=" * 80)
        
        try:
            tickets = self.api.search_tickets(
                from_station=from_station,
                to_station=to_station,
                departure_date=departure_date
            )
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
            return
        
        if not tickets:
            print("Рейсы не найдены.")
            return
        
        print(f"\nНайдено {len(tickets)} рейсов:\n")
        
        for i, train in enumerate(tickets[:10], 1):
            trip = self.api.format_trip_for_card(train)
            duration = self.api.format_duration(trip['duration_minutes'])
            date_ru = self.api.format_datetime_ru(trip['departure_datetime'])
            
            print(f"  {i}. [{trip['train_number']}] {trip['train_name']}")
            print(f"     {trip['departure_time']}–{trip['arrival_time']} "
                  f"({date_ru}) | {duration}")
            print(f"     {trip['from_station']} → {trip['to_station']}")
            print(f"     От {trip['min_price']}₽")
            
            # Доступные вагоны
            summary = self.api.get_available_wagons_summary(train)
            if summary:
                wagon_texts = []
                for w in summary:
                    seats = self.api.format_seats_text(w)
                    wagon_texts.append(f"{w['type_name']} от {w['min_price']}₽ ({seats})")
                print(f"     Вагоны: {', '.join(wagon_texts)}")
            
            print()
    
    def cmd_cars(self, args):
        """Информация о вагонах."""
        if not args:
            print("Укажите параметры. Пример: cars Москва Питер 2026-05-01 06:30 001А")
            return
        
        parts = args.split()
        if len(parts) < 5:
            print("Нужно 5 параметров: откуда куда дата время номер_поезда")
            return
        
        from_station, to_station, departure_date, departure_time, train_number = parts[:5]
        
        print(f"\nВагоны поезда {train_number}: {from_station} → {to_station}, "
              f"{departure_date} {departure_time}")
        print("=" * 60)
        
        try:
            cars_data = self.api.get_carriages(
                from_station=from_station,
                to_station=to_station,
                departure_date=departure_date,
                departure_time=departure_time,
                train_number=train_number
            )
        except Exception as e:
            print(f"Ошибка при получении вагонов: {e}")
            return
        
        cars = cars_data.get('cars', [])
        if not cars:
            print("Информация о вагонах не найдена.")
            return
        
        print(f"\nНайдено {len(cars)} вагонов:\n")
        
        for car in cars:
            wagon = self.api.format_wagon_for_card(car)
            seats_text = self.api.format_seats_text(wagon)
            print(f"  Вагон {wagon['wagon_id']}: {wagon['wagon_type']} "
                  f"({wagon['class']})")
            print(f"  Цена: {wagon['price']}₽ + сбор {wagon['service_fee']}₽")
            print(f"  Места: {seats_text} "
                  f"(всего {wagon['total_available']})")
            print()
    
    def cmd_route(self, args):
        """Станции на маршруте."""
        if not args:
            print("Укажите ID рейса. Пример: route ABC123")
            return
        
        object_id = args.strip()
        print(f"\nМаршрут рейса {object_id}")
        print("=" * 60)
        
        try:
            stations = self.api.get_route_stations(object_id)
        except Exception as e:
            print(f"Ошибка при получении маршрута: {e}")
            return
        
        if not stations:
            print("Информация о маршруте не найдена.")
            return
        
        print(f"\nОстановок: {len(stations)}\n")
        
        for i, s in enumerate(stations, 1):
            arrow = "→" if i < len(stations) else "●"
            print(f"  {i}. {s['station_name']} ({s['station_code']})")
            if s.get('arrival_time'):
                print(f"     Прибытие: {s['arrival_time']}, "
                      f"Отправление: {s['departure_time']}")
            print(f"     {arrow}")
    
    def cmd_exit(self, args):
        """Выход."""
        print("До свидания!")
        sys.exit(0)


# ============================================
# ТОЧКА ВХОДА
# ============================================
if __name__ == '__main__':
    cli = RZDCli()
    cli.run()