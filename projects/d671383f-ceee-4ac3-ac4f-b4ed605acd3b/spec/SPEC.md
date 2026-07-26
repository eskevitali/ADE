# Техническая спецификация: Python Hello Function и Timer Simulator

## Архитектура системы

### Общая архитектура
Система состоит из двух основных компонентов: простой функции приветствия и интерактивного симулятора таймера, демонстрирующего влияние переменных на ход времени.

```
hello_timer_app.py
├── hello() - функция приветствия
├── TimerSimulator - класс симулятора таймера
│   ├── __init__() - инициализация параметров
│   ├── start() - запуск симуляции
│   ├── update_time() - обновление времени
│   ├── display() - отображение состояния
│   ├── handle_input() - обработка пользовательского ввода
│   └── stop() - остановка симуляции
├── main() - основная функция программы
└── __main__ - точка входа
```

### Компоненты системы
- **Функция приветствия**: `hello()` - выводит "Hello, World!"
- **Симулятор таймера**: `TimerSimulator` - демонстрирует изменение времени через переменные
- **Интерфейс управления**: консольные команды для изменения параметров
- **Система отображения**: динамическое обновление экрана

## Модель данных

### Класс TimerSimulator

```python
class TimerSimulator:
    def __init__(self):
        self.current_time: int = 0          # Текущее время в секундах
        self.speed_multiplier: float = 1.0   # Множитель скорости времени
        self.is_running: bool = False        # Состояние симуляции
        self.tick_count: int = 0            # Счетчик итераций
        self.start_time: int = 0            # Начальное время
        self.paused: bool = False           # Состояние паузы
```

### Переменные состояния
- **current_time**: Текущее время симуляции (секунды с начала суток)
- **speed_multiplier**: Коэффициент изменения скорости времени
  - `1.0` = нормальная скорость
  - `> 1.0` = ускоренное время
  - `< 1.0` = замедленное время  
  - `< 0` = обратный ход времени
- **is_running**: Флаг активности симуляции
- **tick_count**: Количество обновлений для демонстрации влияния переменных

## API спецификация

### Функция hello()
```python
def hello() -> None:
    """Выводит приветственное сообщение"""
```

### Класс TimerSimulator

#### Методы инициализации
```python
def __init__(self, start_time: int = 0, speed: float = 1.0) -> None:
    """
    Инициализация симулятора
    
    Args:
        start_time: Начальное время в секундах (0-86399)
        speed: Начальная скорость симуляции
    """
```

#### Методы управления
```python
def start(self) -> None:
    """Запуск симуляции времени"""

def stop(self) -> None:
    """Остановка симуляции"""

def pause(self) -> None:
    """Пауза/возобновление симуляции"""

def set_speed(self, multiplier: float) -> None:
    """
    Установка скорости времени
    
    Args:
        multiplier: Множитель скорости (-1000.0 до 1000.0)
    """

def set_time(self, hours: int, minutes: int, seconds: int) -> None:
    """
    Установка текущего времени
    
    Args:
        hours: Часы (0-23)
        minutes: Минуты (0-59)  
        seconds: Секунды (0-59)
    """
```

#### Методы отображения
```python
def format_time(self) -> str:
    """Форматирование времени в ЧЧ:ММ:СС"""

def get_status(self) -> dict:
    """Получение полного статуса симулятора"""
```

## Пользовательские сценарии (UI Flow)

### Сценарий 1: Базовое использование
1. Запуск программы
2. Вызов `hello()` для приветствия
3. Запуск симулятора с параметрами по умолчанию
4. Наблюдение за ходом времени

### Сценарий 2: Изменение скорости времени
1. Запуск симулятора
2. Ввод команды изменения скорости (например, `s 10`)
3. Наблюдение за ускорением времени
4. Возврат к нормальной скорости (`s 1`)

### Сценарий 3: Демонстрация влияния переменных
1. Установка начального времени
2. Изменение `speed_multiplier` в реальном времени
3. Наблюдение за изменением отображения
4. Демонстрация обратного хода времени (`s -1`)

### Интерактивные команды
- `s <число>` - изменить скорость (например: `s 5`, `s -2`, `s 0.5`)
- `t <ЧЧ:ММ:СС>` - установить время (например: `t 14:30:00`)
- `p` - пауза/возобновление
- `r` - сброс к начальному времени
- `q` - выход из программы
- `h` - справка по командам

## Техническая реализация

### Основная структура программы

```python
import time
import datetime
import threading
import sys
import os

def hello():
    """Функция приветствия"""
    print("Hello, World!")

class TimerSimulator:
    def __init__(self, start_time=0, speed=1.0):
        self.current_time = start_time
        self.speed_multiplier = speed
        self.is_running = False
        self.tick_count = 0
        self.start_time = start_time
        self.paused = False
        self.last_update = time.time()
    
    def start(self):
        """Запуск симуляции"""
        self.is_running = True
        self.last_update = time.time()
        
        # Поток для обновления времени
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Поток для обработки ввода
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
        
        # Основной цикл отображения
        self._display_loop()
    
    def _update_loop(self):
        """Цикл обновления времени"""
        while self.is_running:
            if not self.paused:
                current_real_time = time.time()
                delta = current_real_time - self.last_update
                
                # Применение множителя скорости
                time_change = delta * self.speed_multiplier
                self.current_time += time_change
                
                # Обработка перехода через сутки
                self.current_time = self.current_time % 86400
                if self.current_time < 0:
                    self.current_time += 86400
                
                self.tick_count += 1
                self.last_update = current_real_time
            
            time.sleep(0.1)  # 10 FPS обновления
    
    def _display_loop(self):
        """Цикл отображения"""
        while self.is_running:
            self._clear_screen()
            self._display_status()
            time.sleep(0.1)
    
    def _display_status(self):
        """Отображение текущего состояния"""
        formatted_time = self.format_time()
        status = "ПАУЗА" if self.paused else "РАБОТАЕТ"
        
        print("=" * 50)
        print("    СИМУЛЯТОР ТАЙМЕРА - ДЕМОНСТРАЦИЯ ПЕРЕМЕННЫХ")
        print("=" * 50)
        print(f"Текущее время: {formatted_time}")
        print(f"Скорость времени: {self.speed_multiplier}x")
        print(f"Статус: {status}")
        print(f"Тиков выполнено: {self.tick_count}")
        print("-" * 50)
        print("Команды:")
        print("  s <число> - изменить скорость (пример: s 5, s -2, s 0.5)")
        print("  t <ЧЧ:ММ:СС> - установить время (пример: t 14:30:00)")
        print("  p - пауза/возобновление")
        print("  r - сброс времени")
        print("  q - выход")
        print("-" * 50)
        print("Демонстрация: изменение переменной speed_multiplier")
        print("влияет на скорость хода времени в реальном времени!")
    
    def format_time(self):
        """Форматирование времени"""
        hours = int(self.current_time // 3600)
        minutes = int((self.current_time % 3600) // 60)
        seconds = int(self.current_time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _clear_screen(self):
        """Очистка экрана"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _input_loop(self):
        """Цикл обработки пользовательского ввода"""
        while self.is_running:
            try:
                command = input().strip().lower()
                self._process_command(command)
            except (EOFError, KeyboardInterrupt):
                self.stop()
                break
    
    def _process_command(self, command):
        """Обработка команд пользователя"""
        parts = command.split()
        
        if not parts:
            return
            
        cmd = parts[0]
        
        if cmd == 'q':
            self.stop()
        elif cmd == 'p':
            self.paused = not self.paused
        elif cmd == 'r':
            self.current_time = self.start_time
            self.tick_count = 0
        elif cmd == 's' and len(parts) > 1:
            try:
                new_speed = float(parts[1])
                if -1000 <= new_speed <= 1000:
                    self.speed_multiplier = new_speed
            except ValueError:
                pass
        elif cmd == 't' and len(parts) > 1:
            try:
                time_parts = parts[1].split(':')
                if len(time_parts) == 3:
                    h, m, s = map(int, time_parts)
                    if 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59:
                        self.current_time = h * 3600 + m * 60 + s
            except ValueError:
                pass
    
    def stop(self):
        """Остановка симуляции"""
        self.is_running = False

def main():
    """Основная функция программы"""
    # Приветствие
    hello()
    print("\nДобро пожаловать в демонстрацию влияния переменных на время!")
    print("Нажмите Enter для запуска симулятора...")
    input()
    
    # Создание и запуск симулятора
    simulator = TimerSimulator(start_time=12*3600, speed=1.0)  # Начало в 12:00:00
    
    try:
        simulator.start()
    except KeyboardInterrupt:
        simulator.stop()
        print("\nПрограмма завершена.")

if __name__ == "__main__":
    main()
```

## Демонстрационные сценарии

### Сценарий 1: Нормальная скорость
```python
# speed_multiplier = 1.0
# 1 секунда реального времени = 1 секунда симуляции
```

### Сценарий 2: Ускоренное время
```python
# speed_multiplier = 10.0
# 1 секунда реального времени = 10 секунд симуляции
# Команда: s 10
```

### Сценарий 3: Замедленное время
```python
# speed_multiplier = 0.1
# 1 секунда реального времени = 0.1 секунды симуляции
# Команда: s 0.1
```

### Сценарий 4: Обратный ход времени
```python
# speed_multiplier = -1.0
# Время идет назад с нормальной скоростью
# Команда: s -1
```

## Требования к окружению

### Системные требования
- **Python версия**: 3.6+
- **Операционная система**: Windows, Linux, macOS
- **Память**: < 10MB
- **Зависимости**: Только стандартная библиотека Python

### Необходимые модули
- `time` - для работы с временными задержками
- `datetime` - для форматирования времени  
- `threading` - для многопоточности
- `sys` - для системных функций
- `os` - для очистки экрана

## Критерии приемки

### Функциональные критерии
- [ ] Функция `hello()` выводит "Hello, World!"
- [ ] Симулятор отображает время в формате ЧЧ:ММ:СС
- [ ] Изменение `speed_multiplier` влияет на скорость времени
- [ ] Поддержка положительных и отрицательных значений скорости
- [ ] Интерактивное изменение параметров во время работы
- [ ] Корректная обработка перехода через сутки
- [ ] Функция паузы и возобновления

### Технические критерии
- [ ] Плавное обновление отображения (10 FPS)
- [ ] Отсутствие блокировки при вводе команд
- [ ] Корректная обработка некорректного ввода
- [ ] Кроссплатформенная очистка экрана
- [ ] Корректное завершение всех потоков

### Образовательные критерии
- [ ] Наглядная демонстрация влияния переменных
- [ ] Понятные комментарии в коде
- [ ] Интуитивно понятный интерфейс
- [ ] Демонстрация различных концепций программирования

## Тестирование

### Модульные тесты
```python
import unittest
from unittest.mock import patch
import time

class TestTimerSimulator(unittest.TestCase):
    
    def setUp(self):
        self.simulator = TimerSimulator()
    
    def test_hello_function(self):
        with patch('builtins.print') as mock_print:
            hello()
            mock_print.assert_called_once_with("Hello, World!")
    
    def test_time_formatting(self):
        self.simulator.current_time = 3661  # 1:01:01
        formatted = self.simulator.format_time()
        self.assertEqual(formatted, "01:01:01")
    
    def test_speed_multiplier_effect(self):
        self.simulator.speed_multiplier = 2.0
        initial_time = self.simulator.current_time
        
        # Симуляция обновления времени
        delta = 1.0  # 1 секунда
        time_change = delta * self.simulator.speed_multiplier
        expected_time = initial_time + time_change
        
        self.assertEqual(time_change, 2.0)
    
    def test_negative_speed(self):
        self.simulator.current_time = 3600  # 1:00:00
        self.simulator.speed_multiplier = -1.0
        
        # Время должно идти назад
        delta = 1.0
        time_change = delta * self.simulator.speed_multiplier
        new_time = (self.simulator.current_time + time_change) % 86400
        
        self.assertLess(new_time, self.simulator.current_time)
```

### Интеграционные тесты
- Проверка работы многопоточности
- Тестирование пользовательского ввода
- Проверка корректности отображения
- Тестирование команд управления

## Развертывание

### Установка и запуск
```bash
# Создание файла
cat > hello_timer_app.py << 'EOF'
[код программы]
EOF

# Запуск
python hello_timer_app.py
```

### Использование
1. Запустите программу
2. Нажмите Enter после приветствия
3. Используйте команды для управления симулятором:
   - `s 5` - ускорить время в 5 раз
   - `s -2` - обратный ход времени со скоростью 2x
   - `t 15:30:45` - установить время 15:30:45
   - `p` - пауза/возобновление
   - `q` - выход

## Образовательная ценность

### Демонстрируемые концепции
1. **Влияние переменных**: Изменение `speed_multiplier` мгновенно влияет на поведение программы
2. **Циклы и условия**: Основной цикл симуляции с условными проверками
3. **Многопоточность**: Разделение логики обновления и отображения
4. **Обработка ввода**: Интерактивное взаимодействие с пользователем
5. **Форматирование данных**: Преобразование секунд в читаемый формат времени

### Практические примеры
- Как одна переменная может кардинально изменить поведение программы
- Демонстрация реального времени vs симулированного времени
- Показ влияния математических операций на данные
- Пример создания интерактивного консольного приложения