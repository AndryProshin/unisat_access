
# Unisat Access

Библиотека для организации пользовательского доступа к данным спутниковых архивов, реализованных по технологии UNISAT.

## Структура проекта

```text
📁unisat_access
└── 📁unisat_api        # Основная библиотека
    ├── __init__.py
    ├── config.py       # Настройки (переменные окружения)
    ├── exceptions.py   # Исключения
    ├── metadata.py     # Класс Metadata
    ├── parameters.py   # Класс Parameters
    ├── scene.py        # Класс Scene
    ├── 📁extras        # Опциональные расширения
    │   └── gdal_scene.py     # GDAL расширение для Scene
    └── 📁utils
        └── validators.py # Валидаторы
└── 📁presets           # JSON-файлы пресетов
    └── 📁collections   # Наборы параметров и правил, задающих коллекции данных
    └── 📁user_presets  # Наборы заданных пользователями параметров
└── 📁examples
    ├── test_parameters.py        # Демо работы с классом Parameters
    ├── test_metadata.py          # Демо работы с классами Metadata и Scene
    ├── gdal_example.py           # Демо работы с GDALScene
    ├── check_gdal.py             # Проверка поддержки GDAL
    ├── ndvi_demo.py              # Расчёт и склейка NDVI по сценам
    └── benchmark_read_methods.py # Сравнение методов чтения geotif файлов
└── 📁tests             # Юнит-тесты
└── 📁data              # Выходные данные (создаётся автоматически)
    └── 📁download      # Скачанные фрагменты
    └── 📁processed     # Обработанные данные
├── example.py          # Простейший пример для ознакомления
├── .env.example
├── README.md
└── requirements.txt
```

## Установка

### Требования

```requirements
requests>=2.28.0
python-dotenv>=1.0.0
```

**Примечание:** GDAL не требуется для работы баового функционала библиотеки. Используется для:

* Расширения `GDALScene` (обработка и склейка сцен)
* Примеров `ndvi_demo.py` и `benchmark_read_methods.py`

Установка GDAL при необходимости:

* Linux: `sudo apt install gdal-bin libgdal-dev python3-gdal`
* Windows: `OSGeo4W`

Также вы можете использовать Python из `QGIS`, если нужна встроенная поддержка `GDAL`

## Настройка

Создайте файл .env в корне проекта (указаны демонстрационные адреса):

```dotenv
METADATA_URL=<http://10.10.10.10:8085>
NGINX_URL=<http://10.10.10.10:8095>
```

## Импорт библиотек

```python
import sys
sys.path.insert(0, "путь/к/unisat_access")
from unisat_api import Parameters, Metadata
```

## Основные классы

### Parameters

```python
# Список доступных коллекций
print(Parameters.list_presets())

# Формирование параметров запроса на метаданные для указанной коллекции
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 100,
    "products": ["channel8_l2a", "channel4_l2a"],
    "max_cloudiness": 80
})

# Получить параметры в виде словаря
print(params.to_dict())

# Изменение параметра
params.set("limit", 10)
print(params.get("limit"))

# Информация о параметрах
print(params.get_required_params())
print(params.get_parameters_description())

# Сохранение пользовательского пресета
params.save("my_query")

# Загрузка пользовательского пресета
params2 = Parameters(user_preset="my_query")
print(params2.to_dict())

# Переопределение параметров пользовательского пресета
params3 = Parameters(user_preset="my_query", params={
    "max_cloudiness": 60,
    "limit": 20
})
print(params3.to_dict())
```

### Metadata

```python
# Формирование набора параметров
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-10 00:00:00",
    "bbox": [43, 43, 45, 45],
    "products": ["channel8_l2a", "channel4_l2a"],
    "limit": 2,
    "max_cloudiness": 50
})

# Загрузка метаданных
metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")

# Итерация по сценам
for scene in metadata:
    print(scene.dt, scene.satellite)

# Доступ по индексу
scene = metadata[0]
print(f"Сцена: {scene.dt} | {scene.satellite} | {scene.device}")
print(f"Доступные продукты: {list(scene.products.keys())}")
```

### Scene

Работа со сценой: фрагменты, файлы, ссылки.

```python
# Получение фрагментов с путями к файлам
fragments = scene.get_fragments()
print(f"Фрагментов: {len(fragments)}")
for i, frag in enumerate(fragments):
    print(f"Фрагмент {i}: {frag}")

# Преобразование в HTTP ссылки
http_frag = scene.to_http(fragments[0])
for product, url in http_frag.items():
    print(f"{product}: {url}")

# Преобразование в vsicurl для GDAL
vsicurl_frag = scene.to_vsicurl(fragments[0])

# Скачивание файлов
# С оригинальной структурой
result = scene.download(download_subdir="my_download")
# В плоскую структуру (все файлы в одной папке)
result = scene.download(download_subdir="my_download_flat", flat=True)

# Результат содержит информацию о скачивании
print(f"Директория: {result['download_dir']}")
print(f"Скачано файлов: {len(result['files'])}")
```

### Расширение GDALScene

Требует установки GDAL. Позволяет склеивать фрагменты сцены в один файл, обрезать по bbox и пересэмплировать

```python
from unisat_api.extras import GDALScene

# Создаём параметры запроса (bbox в WGS84 градусах)
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-08-01 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "bbox": [39, 54, 40, 55],  # Рязань в градусах
    "products": ["channel8_l2a", "channel4_l2a"],
    "limit": 2,
    "max_cloudiness": 20
})

# Загружаем метаданные
metadata = Metadata(params)

# Обрабатываем сцены
for scene in metadata:
    gdal_scene = GDALScene(scene)
    
    # Склеиваем фрагменты, обрезаем по bbox, сохраняем
    result = gdal_scene.save_products(
        result_subdir="ryazan_processed",
        resample_to="highest",      # пересэмплировать к максимальному разрешению
        resample_method="bilinear"  # метод пересэмплинга
    )
    
    print(f"Сохранено: {result['files']}")

# Результат в data/processed/ryazan_processed/
#   _params.json      - параметры запроса и обработки
#   _metadata.txt     - лог по сценам
#   20240828_084506_channel8_l2a.tif
#   20240828_084506_channel4_l2a.tif
```

Параметры метода save_products:

|Параметр           | Тип                        | Описание
|-------------------|----------------------------|-----------------------------------------------------------------------------------
|result_subdir      | str                        | Имя поддиректории внутри data/processed/ (обязательный)
|products           | Optional[List[str]]        | Список продуктов для обработки (None → все продукты сцены)
|bbox               | Optional[List[float]]      | [minx, miny, maxx, maxy] в WGS84 градусах (None → из параметров сцены)
|resample_to        | Optional[Union[str, float]]| Пересэмплирование: None (без изменений), `highest`, `lowest`, или число в метрах  
|resample_method    | str                        | Метод пересэмплинга: `nearest`, `bilinear`, `cubic` (по умолчанию *nearest*)
