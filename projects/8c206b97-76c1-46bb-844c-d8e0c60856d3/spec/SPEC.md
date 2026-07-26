# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ
## Мобильное приложение для озвучивания текстовых документов

## Архитектура системы

### Общая архитектура
Приложение построено на архитектуре **MVVM (Model-View-ViewModel)** с использованием **Clean Architecture** принципов:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Presentation  │    │    Domain       │    │      Data       │
│     Layer       │◄──►│     Layer       │◄──►│     Layer       │
│                 │    │                 │    │                 │
│ • Activities    │    │ • Use Cases     │    │ • Repositories  │
│ • Fragments     │    │ • Entities      │    │ • Data Sources  │
│ • ViewModels    │    │ • Repositories  │    │ • Database      │
│ • Adapters      │    │   (Interfaces)  │    │ • File System   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Основные компоненты

#### 1. Presentation Layer
- **MainActivity** - главная активность с навигацией
- **LibraryFragment** - экран библиотеки документов
- **ReaderFragment** - экран чтения документов
- **SettingsFragment** - экран настроек
- **ViewModels** - управление состоянием UI

#### 2. Domain Layer
- **Document** - сущность документа
- **ReadingSession** - сущность сессии чтения
- **Use Cases** - бизнес-логика приложения

#### 3. Data Layer
- **DocumentRepository** - работа с документами
- **FileManager** - управление файлами
- **DatabaseManager** - локальная база данных
- **TTSManager** - управление озвучиванием

## API и интерфейсы

### Внутренние API

#### DocumentRepository Interface
```kotlin
interface DocumentRepository {
    suspend fun getAllDocuments(): List<Document>
    suspend fun getDocumentById(id: String): Document?
    suspend fun addDocument(file: File): Document
    suspend fun deleteDocument(id: String): Boolean
    suspend fun updateDocument(document: Document): Boolean
}
```

#### TTSManager Interface
```kotlin
interface TTSManager {
    fun initialize(context: Context, callback: TTSCallback)
    fun speak(text: String, queueMode: Int)
    fun stop()
    fun pause()
    fun resume()
    fun setSpeed(speed: Float)
    fun setPitch(pitch: Float)
    fun isPlaying(): Boolean
}
```

#### FileParser Interface
```kotlin
interface FileParser {
    fun canParse(file: File): Boolean
    suspend fun parseToText(file: File): String
    fun getSupportedExtensions(): List<String>
}
```

### Внешние API
- **Android TextToSpeech API** - для озвучивания текста
- **Android Storage Access Framework** - для доступа к файлам
- **Apache POI** - для парсинга DOC/DOCX файлов
- **PDFBox Android** - для парсинга PDF файлов

## Модель данных

### Основные сущности

#### Document Entity
```kotlin
@Entity(tableName = "documents")
data class Document(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val title: String,
    val filePath: String,
    val fileType: FileType,
    val fileSize: Long,
    val createdAt: Long = System.currentTimeMillis(),
    val lastOpenedAt: Long? = null,
    val totalPages: Int = 0,
    val totalWords: Int = 0
)

enum class FileType {
    PDF, DOC, DOCX, TXT
}
```

#### ReadingSession Entity
```kotlin
@Entity(tableName = "reading_sessions")
data class ReadingSession(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val documentId: String,
    val currentPosition: Int = 0,
    val currentPage: Int = 1,
    val readingMode: ReadingMode,
    val lastUpdated: Long = System.currentTimeMillis(),
    val readingSpeed: Float = 1.0f,
    val fontSize: Float = 16.0f
)

enum class ReadingMode {
    NORMAL_READING, WORD_BY_WORD, AUDIO_PLAYBACK
}
```

#### ReadingSettings Entity
```kotlin
@Entity(tableName = "reading_settings")
data class ReadingSettings(
    @PrimaryKey val id: Int = 1,
    val defaultFontSize: Float = 16.0f,
    val defaultReadingSpeed: Float = 1.0f,
    val defaultTTSSpeed: Float = 1.0f,
    val defaultTTSPitch: Float = 1.0f,
    val wordByWordDelay: Long = 500L,
    val autoSavePosition: Boolean = true,
    val keepScreenOn: Boolean = true
)
```

### База данных (Room)
```kotlin
@Database(
    entities = [Document::class, ReadingSession::class, ReadingSettings::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun documentDao(): DocumentDao
    abstract fun readingSessionDao(): ReadingSessionDao
    abstract fun settingsDao(): SettingsDao
}
```

## Пользовательские потоки (UI Flows)

### 1. Поток загрузки документа
```
Главный экран → Кнопка "Добавить документ" → 
Выбор файла (File Picker) → Парсинг файла → 
Сохранение в библиотеку → Обновление списка документов
```

### 2. Поток чтения документа
```
Библиотека → Выбор документа → Экран чтения →
Выбор режима чтения → Настройка параметров →
Начало чтения → Сохранение позиции
```

### 3. Поток озвучивания
```
Экран чтения → Кнопка "Диктор" → Инициализация TTS →
Начало озвучивания → Управление воспроизведением →
Сохранение позиции
```

## Детальное описание экранов

### Главный экран (MainActivity)
**Компоненты:**
- BottomNavigationView с вкладками: "Библиотека", "Чтение", "Настройки"
- FloatingActionButton для добавления документов

### Экран библиотеки (LibraryFragment)
**Компоненты:**
- RecyclerView со списком документов
- SearchView для поиска документов
- Меню сортировки (по дате, названию, размеру)
- SwipeRefreshLayout для обновления списка

**Элемент списка документа:**
```xml
<LinearLayout>
    <ImageView android:id="@+id/fileTypeIcon" />
    <LinearLayout android:orientation="vertical">
        <TextView android:id="@+id/documentTitle" />
        <TextView android:id="@+id/documentInfo" />
        <ProgressBar android:id="@+id/readingProgress" />
    </LinearLayout>
    <ImageButton android:id="@+id/menuButton" />
</LinearLayout>
```

### Экран чтения (ReaderFragment)
**Компоненты:**
- ScrollView с текстом документа
- Панель управления (нижняя):
  - SeekBar для скорости чтения
  - Button "Читать/Пауза"
  - Button "Назад" (строка/абзац/страница)
  - Button "Диктор"
- Панель настроек текста:
  - SeekBar размера шрифта
  - Переключатель режимов чтения

**Layout структура:**
```xml
<ConstraintLayout>
    <ScrollView android:id="@+id/textScrollView">
        <TextView android:id="@+id/documentText" />
    </ScrollView>
    
    <LinearLayout android:id="@+id/controlPanel"
                  android:layout_alignParentBottom="true">
        <SeekBar android:id="@+id/speedSeekBar" />
        <ImageButton android:id="@+id/playPauseButton" />
        <ImageButton android:id="@+id/backButton" />
        <ImageButton android:id="@+id/ttsButton" />
    </LinearLayout>
    
    <LinearLayout android:id="@+id/settingsPanel">
        <SeekBar android:id="@+id/fontSizeSeekBar" />
        <ToggleButton android:id="@+id/readingModeToggle" />
    </LinearLayout>
</ConstraintLayout>
```

## Критерии приемки

### Функциональные критерии

#### Управление документами
- ✅ Пользователь может загрузить файлы PDF, DOC, DOCX, TXT
- ✅ Файлы сохраняются в локальную папку приложения
- ✅ Отображается список всех загруженных документов
- ✅ Пользователь может удалить документ из библиотеки
- ✅ Поддерживается поиск документов по названию

#### Режим чтения
- ✅ Текст отображается с возможностью прокрутки
- ✅ Реализовано масштабирование текста (12-24pt)
- ✅ Работает режим "чтение по словам" с настраиваемой скоростью
- ✅ Кнопки "Читать/Пауза" функционируют корректно
- ✅ Реализована навигация назад (строка/абзац/страница)
- ✅ Позиция чтения сохраняется при паузе и закрытии приложения

#### Режим озвучивания
- ✅ TTS инициализируется и работает корректно
- ✅ Кнопки "Слушать/Пауза" функционируют
- ✅ Реализована прокрутка назад в аудио режиме
- ✅ Позиция воспроизведения сохраняется
- ✅ Скорость и тон озвучивания настраиваются

### Технические критерии

#### Производительность
- ✅ Время загрузки документа не превышает 5 секунд
- ✅ Отклик интерфейса не превышает 1 секунды
- ✅ Приложение работает стабильно с файлами до 100 МБ
- ✅ Потребление памяти оптимизировано

#### Совместимость
- ✅ Поддержка Android API 21+
- ✅ Работа на устройствах с разными размерами экранов
- ✅ Совместимость с системными настройками доступности
- ✅ Поддержка различных TTS движков

#### Безопасность и надежность
- ✅ Корректная обработка ошибок парсинга файлов
- ✅ Защита от сбоев при недоступности TTS
- ✅ Сохранение данных при неожиданном закрытии приложения
- ✅ Валидация загружаемых файлов

### UX критерии
- ✅ Интуитивно понятный интерфейс
- ✅ Быстрый доступ к основным функциям
- ✅ Визуальная обратная связь для всех действий
- ✅ Поддержка жестов и горячих клавиш
- ✅ Адаптивность под разные размеры экранов

## Технические детали реализации

### Парсинг документов
```kotlin
class DocumentParserFactory {
    fun createParser(fileType: FileType): FileParser {
        return when (fileType) {
            FileType.PDF -> PDFParser()
            FileType.DOC, FileType.DOCX -> DOCParser()
            FileType.TXT -> TXTParser()
        }
    }
}
```

### Управление TTS
```kotlin
class TTSManagerImpl : TTSManager, TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = null
    private var isInitialized = false
    
    override fun initialize(context: Context, callback: TTSCallback) {
        tts = TextToSpeech(context, this)
    }
    
    override fun onInit(status: Int) {
        isInitialized = (status == TextToSpeech.SUCCESS)
        // Настройка языка и параметров
    }
}
```

### Сохранение позиции чтения
```kotlin
class ReadingPositionManager {
    suspend fun savePosition(documentId: String, position: Int, page: Int) {
        val session = ReadingSession(
            documentId = documentId,
            currentPosition = position,
            currentPage = page,
            lastUpdated = System.currentTimeMillis()
        )
        sessionDao.insertOrUpdate(session)
    }
}
```