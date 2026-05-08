# rzd_cli.py
from datetime import date, datetime, timedelta
from rail_api import RZDApi
import sys
import json


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