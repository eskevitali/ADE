# ТЕХНИЧЕСКОЕ ЗАДАНИЕ
## Мобильное приложение "Я ТУТ v3"

## Цели
- Обеспечить мгновенную отправку GPS-координат пользователя выбранному контакту
- Минимизировать количество действий до отправки координат (один клик)
- Создать простой и интуитивно понятный интерфейс

## Пользователи
- **Основная аудитория**: люди, которым необходимо быстро сообщить свое местоположение (встречи, экстренные ситуации, координация передвижений)
- **Возраст**: 16-65 лет
- **Технические навыки**: базовые навыки работы с мобильными приложениями

## Функции

### Основные функции
- **Захват GPS-координат** устройства в реальном времени
- **Отправка координат** выбранному контакту через настроенный канал связи
- **Настройка контакта** получателя из адресной книги
- **Выбор способа отправки**: SMS, WhatsApp, Telegram

### Интерфейс
- **Главный экран**: одна крупная кнопка "Я ТУТ" в форме цветочка + иконка настроек
- **Экран настроек**: выбор контакта и способа отправки
- **Минималистичный дизайн** без лишних элементов

### Дизайн кнопки "Я ТУТ"
- **Форма**: цветочек с 6 лепестками (гексагональная основа с закругленными краями)
- **Размер**: диаметр 240px (увеличен на 20% от базового размера 200px)
- **Цвет**: фиолетовый градиент для повышенной видимости
- **Градиент**: от светло-фиолетового (#9C27B0) к темно-фиолетовому (#673AB7)
- **Эффекты**: легкая тень для объемности, плавная анимация при нажатии
- **Центр**: текст "Я ТУТ" белым цветом, жирный шрифт

### Настройки по умолчанию
- **Способ отправки по умолчанию**: SMS
- **Пункт в меню настроек**: "Способ отправки: SMS по умолчанию"
- **Логика**: при первом запуске приложения SMS выбран автоматически

## Нефункциональные требования
- **Время отклика**: получение GPS-координат не более 5 секунд
- **Точность**: GPS-координаты с точностью до 10 метров
- **Доступность**: работа без интернета для SMS
- **Простота**: не более 2 тапов для настройки, 1 тап для отправки

## Платформа
- **iOS**: версия 13.0+
- **Android**: версия 7.0+ (API level 24+)
- **Нативная разработка** для оптимальной производительности

## Технические спецификации

### Дизайн-система
```swift
// iOS Constants
struct DesignConstants {
    static let primaryButtonBaseSize: CGFloat = 200
    static let primaryButtonSize: CGFloat = primaryButtonBaseSize * 1.2 // 240px
    static let flowerPetalCount: Int = 6
    static let primaryGradient = LinearGradient(
        colors: [Color(hex: "#9C27B0"), Color(hex: "#673AB7")],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    
    // Flower shape parameters
    static let petalRadius: CGFloat = primaryButtonSize * 0.4
    static let centerRadius: CGFloat = primaryButtonSize * 0.3
    static let petalOverlap: CGFloat = 0.7
}
```

```kotlin
// Android Constants
object DesignConstants {
    const val PRIMARY_BUTTON_BASE_SIZE_DP = 200
    const val PRIMARY_BUTTON_SIZE_DP = (PRIMARY_BUTTON_BASE_SIZE_DP * 1.2).toInt() // 240dp
    const val FLOWER_PETAL_COUNT = 6
    val PRIMARY_GRADIENT = Brush.linearGradient(
        colors = listOf(
            Color(0xFF9C27B0), // Light purple
            Color(0xFF673AB7)  // Dark purple
        )
    )
    
    // Flower shape parameters
    const val PETAL_RADIUS_DP = (PRIMARY_BUTTON_SIZE_DP * 0.4f).toInt()
    const val CENTER_RADIUS_DP = (PRIMARY_BUTTON_SIZE_DP * 0.3f).toInt()
    const val PETAL_OVERLAP = 0.7f
}
```

### Форма цветочка - техническая реализация

#### iOS SwiftUI
```swift
struct FlowerShape: Shape {
    let petalCount: Int = 6
    
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let petalRadius = radius * 0.4
        let centerRadius = radius * 0.3
        
        // Create petals
        for i in 0..<petalCount {
            let angle = Double(i) * (2 * .pi / Double(petalCount))
            let petalCenter = CGPoint(
                x: center.x + cos(angle) * (centerRadius + petalRadius * 0.3),
                y: center.y + sin(angle) * (centerRadius + petalRadius * 0.3)
            )
            
            let petalPath = Path { path in
                path.addEllipse(in: CGRect(
                    x: petalCenter.x - petalRadius,
                    y: petalCenter.y - petalRadius * 0.7,
                    width: petalRadius * 2,
                    height: petalRadius * 1.4
                ))
            }
            path.addPath(petalPath)
        }
        
        // Add center circle
        path.addEllipse(in: CGRect(
            x: center.x - centerRadius,
            y: center.y - centerRadius,
            width: centerRadius * 2,
            height: centerRadius * 2
        ))
        
        return path
    }
}
```

#### Android Compose
```kotlin
@Composable
fun FlowerShape(): GenericShape {
    return GenericShape { size, _ ->
        val center = Offset(size.width / 2f, size.height / 2f)
        val radius = minOf(size.width, size.height) / 2f
        val petalRadius = radius * 0.4f
        val centerRadius = radius * 0.3f
        val petalCount = 6
        
        // Create petals
        for (i in 0 until petalCount) {
            val angle = i * (2 * PI / petalCount).toFloat()
            val petalCenter = Offset(
                center.x + cos(angle) * (centerRadius + petalRadius * 0.3f),
                center.y + sin(angle) * (centerRadius + petalRadius * 0.3f)
            )
            
            addOval(
                Rect(
                    center = petalCenter,
                    radius = petalRadius
                )
            )
        }
        
        // Add center circle
        addOval(
            Rect(
                center = center,
                radius = centerRadius
            )
        )
    }
}
```

### Настройки по умолчанию
```swift
// iOS Default Settings
struct DefaultSettings {
    static let defaultDeliveryMethod: DeliveryMethod = .sms
    static let settingsMenuItems = [
        "Выбрать контакт",
        "Способ отправки: SMS по умолчанию"
    ]
}
```

```kotlin
// Android Default Settings
object DefaultSettings {
    val DEFAULT_DELIVERY_METHOD = DeliveryMethod.SMS
    val SETTINGS_MENU_ITEMS = listOf(
        "Выбрать контакт",
        "Способ отправки: SMS по умолчанию"
    )
}
```

## Ограничения
- Требуются разрешения на доступ к GPS и контактам
- Зависимость от наличия GPS-сигнала
- Для WhatsApp/Telegram требуется интернет-соединение
- Один активный контакт и способ отправки одновременно

## Критерии приемки
- [x] Кнопка "Я ТУТ" имеет форму цветочка с 6 лепестками
- [x] Кнопка увеличена на 20% (диаметр 240px) и имеет фиолетовый градиент
- [x] SMS установлен как способ отправки по умолчанию
- [x] В настройках отображается пункт "Способ отправки: SMS по умолчанию"
- [ ] Время получения GPS не превышает 5 секунд
- [ ] Отправка координат происходит в один клик
- [ ] Приложение работает на указанных версиях платформ
- [ ] Анимация нажатия кнопки-цветочка работает плавно

## Дополнительные требования к форме цветочка
- **Лепестки**: 6 овальных лепестков, расположенных равномерно вокруг центра
- **Пропорции**: лепестки составляют 40% от общего радиуса, центр - 30%
- **Перекрытие**: лепестки слегка перекрывают друг друга для естественного вида
- **Анимация**: при нажатии цветочек слегка "распускается" (увеличивается на 5%) и возвращается в исходное состояние