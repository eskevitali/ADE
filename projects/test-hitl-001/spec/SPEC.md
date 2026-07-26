# Техническая спецификация: Цветная Python Hello Function

## Архитектура системы

### Общая архитектура
Система представляет собой Python модуль с поддержкой цветного вывода, использующий библиотеку colorama для кроссплатформенной совместимости.

```
hello_colorful.py
├── hello() - основная функция с цветным выводом
├── ColoredHello - класс для управления цветами
├── color_demo() - демонстрация всех цветов
└── __main__ - точка входа для демонстрации
```

### Компоненты системы
- **Основная функция**: `hello()` - выполняет цветной вывод приветственного сообщения
- **Класс ColoredHello**: управление цветовой схемой и настройками
- **Демонстрационная функция**: `color_demo()` - показывает все доступные цвета
- **Утилиты**: функции для проверки поддержки цветов терминалом

## Модель данных

### Входные данные
```python
def hello(color: str = "green", message: str = "Hello, World!") -> None
```

### Цветовая схема
```python
COLORS = {
    'red': Fore.RED,
    'green': Fore.GREEN,
    'blue': Fore.BLUE,
    'yellow': Fore.YELLOW,
    'magenta': Fore.MAGENTA,
    'cyan': Fore.CYAN,
    'white': Fore.WHITE,
    'bright_red': Fore.LIGHTRED_EX,
    'bright_green': Fore.LIGHTGREEN_EX,
    'bright_blue': Fore.LIGHTBLUE_EX
}
```

### Структура конфигурации
```python
@dataclass
class HelloConfig:
    default_color: str = "green"
    fallback_enabled: bool = True
    auto_reset: bool = True
    bright_colors: bool = False
```

## API спецификация

### Основные функции

**Функция hello():**
```python
def hello(color: str = "green", message: str = "Hello, World!", 
          style: str = "normal") -> None
```

**Параметры:**
- `color`: Цвет текста (red, green, blue, yellow, magenta, cyan, white)
- `message`: Текст сообщения (по умолчанию "Hello, World!")
- `style`: Стиль текста (normal, bright, dim)

**Функция color_demo():**
```python
def color_demo() -> None
```
Демонстрирует все доступные цвета и стили.

**Класс ColoredHello:**
```python
class ColoredHello:
    def __init__(self, config: HelloConfig = None)
    def print_hello(self, color: str = None, message: str = None) -> None
    def set_default_color(self, color: str) -> None
    def is_color_supported(self) -> bool
```

## Пользовательские сценарии (UI Flow)

### Сценарий 1: Базовое цветное использование
1. Импорт модуля
2. Вызов `hello()` с параметром цвета
3. Получение цветного вывода в консоли

### Сценарий 2: Демонстрация всех цветов
1. Вызов `color_demo()`
2. Просмотр всех доступных цветов
3. Выбор подходящего цвета для использования

### Сценарий 3: Настройка через класс
1. Создание экземпляра `ColoredHello`
2. Настройка параметров по умолчанию
3. Многократное использование с сохраненными настройками

## Техническая реализация

### Основная реализация
```python
from colorama import init, Fore, Style, Back
import sys
import os
from dataclasses import dataclass
from typing import Optional

# Инициализация colorama для Windows
init(autoreset=True)

@dataclass
class HelloConfig:
    default_color: str = "green"
    fallback_enabled: bool = True
    auto_reset: bool = True
    bright_colors: bool = False

class ColoredHello:
    COLORS = {
        'red': Fore.RED,
        'green': Fore.GREEN,
        'blue': Fore.BLUE,
        'yellow': Fore.YELLOW,
        'magenta': Fore.MAGENTA,
        'cyan': Fore.CYAN,
        'white': Fore.WHITE,
        'bright_red': Fore.LIGHTRED_EX,
        'bright_green': Fore.LIGHTGREEN_EX,
        'bright_blue': Fore.LIGHTBLUE_EX,
        'bright_yellow': Fore.LIGHTYELLOW_EX,
        'bright_magenta': Fore.LIGHTMAGENTA_EX,
        'bright_cyan': Fore.LIGHTCYAN_EX
    }
    
    STYLES = {
        'normal': Style.NORMAL,
        'bright': Style.BRIGHT,
        'dim': Style.DIM
    }
    
    def __init__(self, config: HelloConfig = None):
        self.config = config or HelloConfig()
        self._check_color_support()
    
    def _check_color_support(self) -> bool:
        """Проверяет поддержку цветов терминалом"""
        return (
            hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and
            os.getenv('TERM') != 'dumb' and
            os.name != 'nt' or os.getenv('ANSICON') is not None
        )
    
    def print_hello(self, color: str = None, message: str = None, 
                   style: str = "normal") -> None:
        color = color or self.config.default_color
        message = message or "Hello, World!"
        
        if not self._check_color_support() and self.config.fallback_enabled:
            print(message)
            return
        
        color_code = self.COLORS.get(color.lower(), self.COLORS['green'])
        style_code = self.STYLES.get(style.lower(), self.STYLES['normal'])
        
        colored_message = f"{style_code}{color_code}{message}"
        if self.config.auto_reset:
            colored_message += Style.RESET_ALL
        
        print(colored_message)

# Глобальный экземпляр для простого использования
_default_hello = ColoredHello()

def hello(color: str = "green", message: str = "Hello, World!", 
          style: str = "normal") -> None:
    """Выводит цветное приветственное сообщение"""
    _default_hello.print_hello(color, message, style)

def color_demo() -> None:
    """Демонстрирует все доступные цвета"""
    print("🎨 Демонстрация цветов:")
    print("-" * 30)
    
    for color_name in ColoredHello.COLORS.keys():
        hello(color_name, f"Hello in {color_name}!")
    
    print("\n🎭 Демонстрация стилей:")
    print("-" * 30)
    
    for style_name in ColoredHello.STYLES.keys():
        hello("cyan", f"Hello in {style_name} style!", style_name)

def set_default_color(color: str) -> None:
    """Устанавливает цвет по умолчанию"""
    _default_hello.config.default_color = color

if __name__ == "__main__":
    print("🌈 Цветная Hello Function")
    print("=" * 40)
    
    # Базовая демонстрация
    hello()
    hello("red", "Привет, мир!")
    hello("blue", "Hello, Python!", "bright")
    
    print("\n")
    color_demo()
```

### Упрощенная версия без внешних зависимостей
```python
import sys
import os

class SimpleColoredHello:
    # ANSI escape коды
    COLORS = {
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m',
        'reset': '\033[0m'
    }
    
    @classmethod
    def hello(cls, color: str = "green", message: str = "Hello, World!") -> None:
        if cls._supports_color():
            color_code = cls.COLORS.get(color.lower(), cls.COLORS['green'])
            print(f"{color_code}{message}{cls.COLORS['reset']}")
        else:
            print(message)
    
    @staticmethod
    def _supports_color() -> bool:
        return (
            hasattr(sys.stdout, 'isatty') and 
            sys.stdout.isatty() and 
            os.getenv('TERM') != 'dumb'
        )

# Простая функция для использования
def hello(color: str = "green", message: str = "Hello, World!") -> None:
    SimpleColoredHello.hello(color, message)
```

## Требования к окружению

### Системные требования
- **Python версия**: 3.6+ (для dataclasses и type hints)
- **Операционная система**: Windows, Linux, macOS
- **Память**: < 5MB
- **Зависимости**: colorama (рекомендуется) или встроенные ANSI коды

### Установка зависимостей
```bash
pip install colorama
```

### Совместимость терминалов
- **Windows**: Command Prompt, PowerShell, Windows Terminal
- **Linux**: bash, zsh, fish, различные эмуляторы терминала
- **macOS**: Terminal.app, iTerm2
- **IDE**: PyCharm, VS Code, Jupyter Notebook

## Критерии приемки

### Функциональные критерии
- [ ] Функция выводит цветное приветственное сообщение
- [ ] Поддерживает минимум 6 основных цветов
- [ ] Работает на Windows, Linux, macOS
- [ ] Graceful fallback для терминалов без поддержки цветов
- [ ] Автоматическое восстановление цвета после вывода
- [ ] Возможность настройки цвета и сообщения

### Технические критерии
- [ ] Код совместим с Python 3.6+
- [ ] Использует colorama или ANSI коды
- [ ] Проверяет поддержку цветов терминалом
- [ ] Обрабатывает некорректные названия цветов
- [ ] Функция выполняется без ошибок во всех окружениях

### Критерии качества
- [ ] Код читаемый и хорошо документирован
- [ ] Соответствует PEP 8
- [ ] Включает примеры использования
- [ ] Имеет демонстрационную функцию
- [ ] Подходит для обучения начинающих

## Тестирование

### Модульные тесты
```python
import unittest
from unittest.mock import patch
import io
import sys
from contextlib import redirect_stdout

class TestColoredHello(unittest.TestCase):
    
    def test_hello_basic_output(self):
        """Тест базового вывода"""
        with patch('sys.stdout.isatty', return_value=False):
            f = io.StringIO()
            with redirect_stdout(f):
                hello()
            self.assertEqual(f.getvalue().strip(), "Hello, World!")
    
    def test_hello_custom_message(self):
        """Тест пользовательского сообщения"""
        with patch('sys.stdout.isatty', return_value=False):
            f = io.StringIO()
            with redirect_stdout(f):
                hello(message="Test message")
            self.assertEqual(f.getvalue().strip(), "Test message")
    
    def test_color_support_detection(self):
        """Тест определения поддержки цветов"""
        colored_hello = ColoredHello()
        result = colored_hello._check_color_support()
        self.assertIsInstance(result, bool)
    
    def test_invalid_color_fallback(self):
        """Тест fallback для некорректного цвета"""
        with patch('sys.stdout.isatty', return_value=True):
            f = io.StringIO()
            with redirect_stdout(f):
                hello("invalid_color")
            # Должен использовать цвет по умолчанию
            self.assertIn("Hello, World!", f.getvalue())

if __name__ == '__main__':
    unittest.main()
```

### Интеграционные тесты
```python
def test_cross_platform_compatibility():
    """Тест кроссплатформенной совместимости"""
    import platform
    
    system = platform.system()
    hello("green", f"Testing on {system}")
    
    # Тест должен пройти без исключений на всех платформах

def test_terminal_compatibility():
    """Тест совместимости с различными терминалами"""
    import os
    
    # Сохраняем оригинальные переменные окружения
    original_term = os.getenv('TERM')
    
    # Тестируем различные значения TERM
    test_terms = ['xterm', 'xterm-256color', 'dumb', None]
    
    for term in test_terms:
        os.environ['TERM'] = term or ''
        try:
            hello("blue", f"Testing with TERM={term}")
        except Exception as e:
            print(f"Error with TERM={term}: {e}")
        finally:
            if original_term:
                os.environ['TERM'] = original_term
```

## Развертывание

### Установка через pip (если создан пакет)
```bash
pip install colorful-hello
```

### Прямое использование
```python
# Скачать файл hello_colorful.py
# Импортировать в проект
from hello_colorful import hello, color_demo

hello("red", "Привет!")
color_demo()
```

### Создание исполняемого файла
```bash
# Создание standalone скрипта
python -m PyInstaller --onefile hello_colorful.py
```

## Документация

### Примеры использования

**Базовое использование:**
```python
from hello_colorful import hello

# Стандартное зеленое приветствие
hello()

# Красное приветствие
hello("red")

# Пользовательское сообщение
hello("blue", "Добро пожаловать!")

# С ярким стилем
hello("yellow", "Внимание!", "bright")
```

**Продвинутое использование:**
```python
from hello_colorful import ColoredHello, HelloConfig

# Настройка конфигурации
config = HelloConfig(
    default_color="cyan",
    bright_colors=True,
    fallback_enabled=True
)

# Создание настроенного экземпляра
colored_hello = ColoredHello(config)
colored_hello.print_hello()

# Демонстрация всех цветов
from hello_colorful import color_demo
color_demo()
```

**Интеграция в приложение:**
```python
#!/usr/bin/env python3
from hello_colorful import hello

def main():
    print("🚀 Запуск приложения...")
    hello("green", "Приложение успешно запущено!")
    
    # Основная логика приложения
    
    hello("blue", "Работа завершена!", "bright")

if __name__ == "__main__":
    main()
```

### Изменения в реализации

**Что изменилось по сравнению с предыдущей версией:**

1. **Добавлена поддержка цветов** - основное требование
2. **Добавлены параметры функции** - цвет, сообщение, стиль
3. **Добавлен класс ColoredHello** - для продвинутого управления
4. **Добавлена функция color_demo()** - демонстрация возможностей
5. **Добавлена проверка поддержки цветов** - graceful fallback
6. **Добавлена зависимость colorama** - кроссплатформенность
7. **Расширены тесты** - покрытие новой функциональности
8. **Обновлена документация** - примеры цветного использования

**Обратная совместимость:**
- Функция `hello()` без параметров работает как раньше, но теперь в цвете
- Добавлены опциональные параметры, не нарушающие существующий код