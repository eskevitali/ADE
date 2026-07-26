# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ
## Мобильное приложение "Я ТУТ v3"

## Архитектура системы

### Общая архитектура
- **Паттерн**: MVVM (Model-View-ViewModel)
- **iOS**: SwiftUI + Combine
- **Android**: Jetpack Compose + ViewModel + LiveData
- **Локальное хранение**: UserDefaults (iOS) / SharedPreferences (Android)
- **Без серверной части** - полностью автономное приложение

### Структура модулей

#### iOS (Swift)
```
YaTutApp/
├── Models/
│   ├── Contact.swift
│   ├── DeliveryMethod.swift
│   └── LocationData.swift
├── ViewModels/
│   ├── MainViewModel.swift
│   └── SettingsViewModel.swift
├── Views/
│   ├── MainView.swift
│   ├── SettingsView.swift
│   └── Components/
│       ├── FlowerButton.swift (НОВЫЙ)
│       └── FlowerShape.swift (НОВЫЙ)
├── Services/
│   ├── LocationService.swift
│   ├── ContactService.swift
│   └── MessageService.swift
└── Utils/
    ├── Permissions.swift
    ├── Constants.swift
    └── DesignSystem.swift
```

#### Android (Kotlin)
```
com.yatut.app/
├── data/
│   ├── models/
│   ├── repositories/
│   └── local/
├── domain/
│   ├── entities/
│   ├── usecases/
│   └── repositories/
├── presentation/
│   ├── ui/
│   │   ├── main/
│   │   ├── settings/
│   │   └── components/
│   │       ├── FlowerButton.kt (НОВЫЙ)
│   │       └── FlowerShape.kt (НОВЫЙ)
│   ├── viewmodels/
│   └── theme/
│       └── DesignSystem.kt
└── services/
    ├── LocationService.kt
    ├── ContactService.kt
    └── MessageService.kt
```

## Модель данных

### Основные сущности

#### Contact (Контакт)
```kotlin
data class Contact(
    val id: String,
    val name: String,
    val phoneNumber: String,
    val displayName: String
)
```

#### DeliveryMethod (Способ доставки)
```kotlin
enum class DeliveryMethod(val displayName: String) {
    SMS("SMS по умолчанию"),
    WHATSAPP("WhatsApp"),
    TELEGRAM("Telegram")
}
```

#### LocationData (Данные местоположения)
```kotlin
data class LocationData(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val timestamp: Long,
    val address: String? = null
)
```

#### AppSettings (Настройки приложения)
```kotlin
data class AppSettings(
    val selectedContact: Contact?,
    val deliveryMethod: DeliveryMethod = DeliveryMethod.SMS,
    val isFirstLaunch: Boolean = true
)
```

### Локальное хранение

#### iOS (UserDefaults)
- `selected_contact_id`: String
- `selected_contact_name`: String  
- `selected_contact_phone`: String
- `delivery_method`: String (по умолчанию "SMS")
- `is_first_launch`: Bool

#### Android (SharedPreferences)
- `selected_contact_id`: String
- `selected_contact_name`: String
- `selected_contact_phone`: String
- `delivery_method`: String (по умолчанию "SMS")
- `is_first_launch`: Boolean

## Дизайн-система

### Константы дизайна для кнопки-цветочка

#### iOS (SwiftUI)
```swift
struct DesignConstants {
    // Размеры кнопки-цветочка
    static let primaryButtonBaseSize: CGFloat = 200
    static let primaryButtonSize: CGFloat = primaryButtonBaseSize * 1.2 // 240px
    static let flowerPetalCount: Int = 6
    
    // Параметры цветочка
    static let petalRadius: CGFloat = primaryButtonSize * 0.4 // 96px
    static let centerRadius: CGFloat = primaryButtonSize * 0.3 // 72px
    static let petalOverlap: CGFloat = 0.7
    
    // Цвета и градиенты
    static let primaryGradient = LinearGradient(
        colors: [
            Color(hex: "#9C27B0"), // Светло-фиолетовый
            Color(hex: "#673AB7")  // Темно-фиолетовый
        ],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    
    // Тени
    static let primaryButtonShadow = Shadow(
        color: Color.black.opacity(0.3),
        radius: 8,
        x: 0,
        y: 4
    )
    
    // Типографика
    static let primaryButtonFont = Font.system(size: 24, weight: .bold)
    
    // Анимация "распускания"
    static let bloomScale: CGFloat = 1.05
    static let bloomDuration: Double = 0.15
}
```

#### Android (Jetpack Compose)
```kotlin
object DesignConstants {
    // Размеры кнопки-цветочка
    const val PRIMARY_BUTTON_BASE_SIZE_DP = 200
    const val PRIMARY_BUTTON_SIZE_DP = (PRIMARY_BUTTON_BASE_SIZE_DP * 1.2).toInt() // 240dp
    const val FLOWER_PETAL_COUNT = 6
    
    // Параметры цветочка
    const val PETAL_RADIUS_DP = (PRIMARY_BUTTON_SIZE_DP * 0.4f).toInt() // 96dp
    const val CENTER_RADIUS_DP = (PRIMARY_BUTTON_SIZE_DP * 0.3f).toInt() // 72dp
    const val PETAL_OVERLAP = 0.7f
    
    // Цвета и градиенты
    val PRIMARY_GRADIENT = Brush.linearGradient(
        colors = listOf(
            Color(0xFF9C27B0), // Светло-фиолетовый
            Color(0xFF673AB7)  // Темно-фиолетовый
        ),
        start = Offset(0f, 0f),
        end = Offset(Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY)
    )
    
    // Тени
    const val PRIMARY_BUTTON_ELEVATION_DP = 8
    
    // Типографика
    val PRIMARY_BUTTON_TEXT_STYLE = TextStyle(
        fontSize = 24.sp,
        fontWeight = FontWeight.Bold,
        color = Color.White
    )
    
    // Анимация "распускания"
    const val BLOOM_SCALE = 1.05f
    const val BLOOM_DURATION_MS = 150
}
```

### Форма цветочка - техническая реализация

#### iOS SwiftUI - FlowerShape
```swift
struct FlowerShape: Shape {
    let petalCount: Int = DesignConstants.flowerPetalCount
    
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let petalRadius = DesignConstants.petalRadius
        let centerRadius = DesignConstants.centerRadius
        
        // Создаем лепестки
        for i in 0..<petalCount {
            let angle = Double(i) * (2 * .pi / Double(petalCount))
            let petalCenter = CGPoint(
                x: center.x + cos(angle) * (centerRadius + petalRadius * 0.3),
                y: center.y + sin(angle) * (centerRadius + petalRadius * 0.3)
            )
            
            // Овальный лепесток
            let petalRect = CGRect(
                x: petalCenter.x - petalRadius * 0.6,
                y: petalCenter.y - petalRadius,
                width: petalRadius * 1.2,
                height: petalRadius * 2
            )
            
            // Поворачиваем лепесток по направлению от центра
            let transform = CGAffineTransform(translationX: petalCenter.x, y: petalCenter.y)
                .rotated(by: angle)
                .translatedBy(x: -petalCenter.x, y: -petalCenter.y)
            
            let petalPath = Path(ellipseIn: petalRect).applying(transform)
            path.addPath(petalPath)
        }
        
        // Добавляем центральный круг
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

#### Android Compose - FlowerShape
```kotlin
class FlowerShape : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density
    ): Outline {
        val path = Path()
        val center = Offset(size.width / 2f, size.height / 2f)
        val radius = minOf(size.width, size.height) / 2f
        val petalRadius = radius * 0.4f
        val centerRadius = radius * 0.3f
        val petalCount = DesignConstants.FLOWER_PETAL_COUNT
        
        // Создаем лепестки
        for (i in 0 until petalCount) {
            val angle = i * (2 * PI / petalCount).toFloat()
            val petalCenter = Offset(
                center.x + cos(angle) * (centerRadius + petalRadius * 0.3f),
                center.y + sin(angle) * (centerRadius + petalRadius * 0.3f)
            )
            
            // Овальный лепесток
            val petalRect = Rect(
                center = petalCenter,
                radius = petalRadius
            ).let { rect ->
                Rect(
                    left = rect.left - petalRadius * 0.2f,
                    top = rect.top - petalRadius * 0.5f,
                    right = rect.right + petalRadius * 0.2f,
                    bottom = rect.bottom + petalRadius * 0.5f
                )
            }
            
            // Поворачиваем лепесток
            path.addOval(petalRect)
        }
        
        // Добавляем центральный круг
        path.addOval(
            Rect(
                center = center,
                radius = centerRadius
            )
        )
        
        return Outline.Generic(path)
    }
}
```

### Компонент кнопки-цветочка

#### iOS (SwiftUI) - FlowerButton
```swift
struct FlowerButton: View {
    let title: String
    let action: () -> Void
    @State private var isPressed = false
    @State private var isBloomAnimating = false
    
    var body: some View {
        Button(action: {
            // Анимация "распускания"
            withAnimation(.easeInOut(duration: DesignConstants.bloomDuration)) {
                isBloomAnimating = true
            }
            
            // Возврат к исходному размеру
            DispatchQueue.main.asyncAfter(deadline: .now() + DesignConstants.bloomDuration) {
                withAnimation(.easeInOut(duration: DesignConstants.bloomDuration)) {
                    isBloomAnimating = false
                }
            }
            
            action()
        }) {
            Text(title)
                .font(DesignConstants.primaryButtonFont)
                .foregroundColor(.white)
                .frame(
                    width: DesignConstants.primaryButtonSize,
                    height: DesignConstants.primaryButtonSize
                )
                .background(
                    FlowerShape()
                        .fill(DesignConstants.primaryGradient)
                        .shadow(
                            color: DesignConstants.primaryButtonShadow.color,
                            radius: DesignConstants.primaryButtonShadow.radius,
                            x: DesignConstants.primaryButtonShadow.x,
                            y: DesignConstants.primaryButtonShadow.y
                        )
                )
                .scaleEffect(isPressed ? 0.95 : (isBloomAnimating ? DesignConstants.bloomScale : 1.0))
        }
        .buttonStyle(PlainButtonStyle())
        .onLongPressGesture(minimumDuration: 0, maximumDistance: .infinity, pressing: { pressing in
            withAnimation(.easeInOut(duration: 0.1)) {
                isPressed = pressing
            }
        }, perform: {})
    }
}
```

#### Android (Jetpack Compose) - FlowerButton
```kotlin
@Composable
fun FlowerButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    var isPressed by remember { mutableStateOf(false) }
    var isBloomAnimating by remember { mutableStateOf(false) }
    
    val scale by animateFloatAsState(
        targetValue = when {
            isPressed -> 0.95f
            isBloomAnimating -> DesignConstants.BLOOM_SCALE
            else -> 1f
        },
        animationSpec = tween(
            durationMillis = if (isBloomAnimating) DesignConstants.BLOOM_DURATION_MS else 100
        )
    )
    
    Box(
        modifier = modifier
            .size(DesignConstants.PRIMARY_BUTTON_SIZE_DP.dp)
            .scale(scale)
            .clip(FlowerShape())
            .background(
                brush = DesignConstants.PRIMARY_GRADIENT
            )
            .shadow(
                elevation = DesignConstants.PRIMARY_BUTTON_ELEVATION_DP.dp,
                shape = FlowerShape()
            )
            .clickable {
                // Анимация "распускания"
                isBloomAnimating = true
                
                // Возврат к исходному размеру
                CoroutineScope(Dispatchers.Main).launch {
                    delay(DesignConstants.BLOOM_DURATION_MS.toLong())
                    isBloomAnimating = false
                }
                
                onClick()
            }
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        isPressed = true
                        tryAwaitRelease()
                        isPressed = false
                    }
                )
            },
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            style = DesignConstants.PRIMARY_BUTTON_TEXT_STYLE
        )
    }
}
```

## API и сервисы

### LocationService
```kotlin
interface LocationService {
    suspend fun getCurrentLocation(): Result<LocationData>
    fun requestLocationPermission(): Boolean
    fun isLocationPermissionGranted(): Boolean
}
```

### ContactService  
```kotlin
interface ContactService {
    suspend fun getContacts(): List<Contact>
    fun requestContactsPermission(): Boolean
    fun isContactsPermissionGranted(): Boolean
}
```

### MessageService
```kotlin
interface MessageService {
    fun sendSMS(contact: Contact, message: String): Boolean
    fun sendWhatsApp(contact: Contact, message: String): Boolean  
    fun sendTelegram(contact: Contact, message: String): Boolean
    fun isAppInstalled(deliveryMethod: DeliveryMethod): Boolean
}
```

### SettingsService
```kotlin
interface SettingsService {
    fun getDefaultSettings(): AppSettings
    fun saveSettings(settings: AppSettings)
    fun getDeliveryMethodDisplayName(method: DeliveryMethod): String
}
```

## Пользовательские потоки (UI Flows)

### Первый запуск приложения
1. **Экран приветствия** (опционально)
2. **Запрос разрешений** на геолокацию и контакты
3. **Настройка контакта** - выбор из адресной книги
4. **Автоматическая установка SMS** как способа отправки по умолчанию
5. **Переход на главный экран**

### Основной поток использования
1. **Главный экран** - отображение кнопки-цветочка с фиолетовым градиентом
2. **Нажатие кнопки** - анимация "распускания" + захват GPS-координат
3. **Индикатор загрузки** (до 5 секунд)
4. **Отправка сообщения** через выбранный канал
5. **Уведомление об успехе/ошибке**

### Поток настроек
1. **Нажатие иконки настроек**
2. **Экран настроек** с пунктом "Способ отправки: SMS по умолчанию"
3. **Изменение контакта** - выбор из списка
4. **Изменение способа доставки** - обновление отображаемого текста
5. **Сохранение настроек** - автоматически

## Дизайн интерфейса

### Главный экран (с кнопкой-цветочком)
```
┌─────────────────────────┐
│  [⚙️]              [?] │ <- Настройки и помощь
│                         │
│                         │
│       🌸               │ <- Кнопка-цветочек
│    ╭─╮ ╭─╮             │    с 6 лепестками
│  ╭─╯   ╰─╮             │    фиолетовый градиент
│  │ Я ТУТ │             │    размер 240x240dp
│  ╰─╮   ╭─╯             │    с тенью
│    ╰─╯ ╰─╯             │
│       🌸               │
│                         │
│  📍 Готов к отправке    │ <- Статус
│  👤 Мама • 📱 SMS       │ <- Текущие настройки
└─────────────────────────┘
```

### Экран настроек
```
┌─────────────────────────┐
│  [←] Настройки          │
│                         │
│  👤 Контакт             │
│  ┌─────────────────────┐│
│  │ Мама                ││ <- Выбранный контакт
│  │ +7 (999) 123-45-67  ││
│  └─────────────────────┘│
│  [Изменить контакт]     │
│                         │
│  📱 Способ отправки:    │
│      SMS по умолчанию   │
│  ○ SMS по умолчанию     │
│  ● WhatsApp             │
│  ○ Telegram             │
│                         │
│  [Тест отправки]        │
└─────────────────────────┘
```

## Технические требования

### Разрешения

#### iOS (Info.plist)
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Приложение использует геолокацию для отправки ваших координат</string>
<key>NSContactsUsageDescription</key>
<string>Приложение использует контакты для выбора получателя</string>
```

#### Android (AndroidManifest.xml)
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.READ_CONTACTS" />
<uses-permission android:name="android.permission.SEND_SMS" />
```

### Производительность
- **Время получения GPS**: максимум 5 секунд
- **Точность координат**: до 10 метров
- **Размер приложения**: не более 50 МБ
- **Потребление батареи**: минимальное (GPS только по запросу)

### Совместимость
- **iOS**: 13.0+ (iPhone 6s и новее)
- **Android**: API 24+ (Android 7.0+)
- **Поддержка**: iPhone SE, все современные Android устройства

## Изменения в реализации

### Что нужно изменить в существующем коде:

#### 1. НОВЫЕ компоненты кнопки-цветочка
- **Создать FlowerShape.swift/kt** - кастомная форма цветочка с 6 лепестками
- **Создать FlowerButton.swift/kt** - компонент кнопки с анимацией "распускания"
- **Обновить DesignSystem** - добавить константы для цветочка

#### 2. Параметры цветочка
- **6 лепестков** расположенных равномерно (60° между лепестками)
- **Размер**: общий диаметр 240dp, лепестки 96dp, центр 72dp
- **Форма лепестков**: овальная с соотношением 1:2 (ширина:высота)
- **Перекрытие**: лепестки слегка перекрывают друг друга (коэффициент 0.7)

#### 3. Анимация "распускания"
- **При нажатии**: цветочек увеличивается на 5% (scale 1.05)
- **Длительность**: 150ms туда и обратно
- **Easing**: easeInOut для плавности
- **Дополнительно**: обычная анимация нажатия (scale 0.95) при удержании

#### 4. Компоненты для создания/обновления
```
iOS (НОВЫЕ):
- Views/Components/FlowerShape.swift
- Views/Components/FlowerButton.swift

iOS (ОБНОВИТЬ):
- Views/MainView.swift (заменить PrimaryButton на FlowerButton)
- Utils/DesignSystem.swift (добавить константы цветочка)

Android (НОВЫЕ):
- presentation/ui/components/FlowerShape.kt
- presentation/ui/components/FlowerButton.kt

Android (ОБНОВИТЬ):
- presentation/ui/main/MainScreen.kt (заменить PrimaryButton на FlowerButton)
- presentation/theme/DesignSystem.kt (добавить константы цветочка)
```

#### 5. Техническая реализация цветочка
- **Математика**: использование тригонометрии для расположения лепестков
- **Отрисовка**: комбинация овалов (лепестки) + круг (центр)
- **Градиент**: применяется ко всей форме цветочка
- **Тень**: повторяет форму цветочка, а не прямоугольника

## Критерии приемки

### Функциональные критерии

#### Основная функциональность
- ✅ Приложение получает GPS-координаты за 5 секунд или менее
- ✅ Координаты отправляются выбранному контакту в один клик
- ✅ Поддерживаются все три способа отправки: SMS, WhatsApp, Telegram
- ✅ SMS установлен как способ отправки по умолчанию
- ✅ Настройки сохраняются между сессиями

#### Интерфейс кнопки-цветочка (НОВЫЕ требования)
- ✅ Кнопка имеет форму цветочка с 6 лепестками
- ✅ Общий размер кнопки 240dp (увеличен на 20%)
- ✅ Лепестки имеют овальную форму и равномерно распределены
- ✅ Кнопка имеет фиолетовый градиент (#9C27B0 → #673AB7)
- ✅ Кнопка имеет тень, повторяющую форму цветочка
- ✅ При нажатии цветочек "распускается" (увеличивается на 5%)
- ✅ Анимация распускания длится 150ms и плавно возвращается
- ✅ В настройках отображается "Способ отправки: SMS по умолчанию"

#### Разрешения и безопасность
- ✅ Приложение корректно запрашивает разрешения на геолокацию и контакты
- ✅ Работает без интернета при использовании SMS
- ✅ Обрабатывает отсутствие GPS-сигнала с понятным сообщением
- ✅ Проверяет установку мессенджеров перед попыткой отправки

### Нефункциональные критерии

#### Производительность
- ✅ Приложение запускается за 2 секунды или менее
- ✅ Отправка координат происходит без задержек после получения GPS
- ✅ Интерфейс отзывчивый, без заметных лагов
- ✅ Анимация цветочка работает плавно на 60fps

#### Надежность  
- ✅ Приложение не крашится при отсутствии интернета
- ✅ Корректно обрабатывает отказ в разрешениях
- ✅ Восстанавливает настройки после перезапуска
- ✅ SMS устанавливается по умолчанию при первом запуске

#### Удобство использования
- ✅ Интуитивно понятный интерфейс без обучения
- ✅ Четкие сообщения об ошибках и статусе операций
- ✅ Поддержка темной и светлой темы (следует системным настройкам)
- ✅ Кнопка-цветочек привлекательна и легко узнаваема

### Тестовые сценарии (обновленные для цветочка)

#### Сценарий 1: Первое использование с кнопкой-цветочком
1. Установить приложение
2. Проверить автоматическую установку SMS по умолчанию
3. Предоставить разрешения на геолокацию и контакты
4. Выбрать контакт из адресной книги
5. Проверить отображение кнопки-цветочка с 6 лепестками
6. Проверить фиолетовый градиент и тень
7. Нажать кнопку-цветочек на главном экране
8. Проверить получение SMS с координатами

#### Сценарий 2: Тестирование анимации цветочка
1. Открыть главный экран
2. Проверить форму цветочка (6 лепестков, овальные)
3. Нажать и удерживать кнопку - проверить анимацию сжатия (scale 0.95)
4. Отпустить - проверить анимацию "распускания" (scale 1.05)
5. Проверить плавный возврат к исходному размеру
6. Проверить, что анимация не мешает отправке координат

#### Сценарий 3: Проверка настроек по умолчанию
1. Открыть настройки
2. Проверить отображение "Способ отправки: SMS по умолчанию"
3. Проверить выбор SMS в радио-кнопках
4. Изменить на WhatsApp
5. Проверить обновление заголовка на "Способ отправки: WhatsApp"
6. Вернуться на главный экран и проверить отправку через кнопку-цветочек