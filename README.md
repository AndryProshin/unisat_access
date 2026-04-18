
# Unisat Access

Библиотека для организации пользовательского доступа к данным спутниковых архивов, реализованных по технологии UNISAT.

## Структура проекта

```text
📁unisat_access
├── 📁unisat_api
│   ├── config.py                   # Настройки, переменные окружения
│   ├── parameters.py               # Класс Parameters (общий для всех запросов)
│   ├── metadata.py                 # Класс Metadata (архивный режим, поиск сцен)
│   ├── scene.py                    # Класс Scene (архивный режим, фрагменты)
├── 📁processing
│   ├── 📁gdal
│   │   ├── utils.py                # Чтение/запись GeoTIFF, утилиты
│   │   └── scene.py                # GDALScene (склейка, обрезка)
│   ├── 📁indices
│   │   ├── base.py                 # SpectralIndex, IndexCalculator
│   │   └── sentinel2.py            # Sentinel2Indices, compute_ndvi и др.
│   └── 📁masks
│       ├── base.py                 # Mask (универсальный класс)
│       └── sentinel2.py            # SCL маски для Sentinel-2
├── 📁presets
│   ├── 📁collections               # Параметры (пресеты) коллекций (sentinel2_boa и др.)
│   └── 📁user_presets              # Пользовательские пресеты
├── 📁examples
│   ├── parameters_demo.py          # Демо работы с Parameters
│   ├── metadata_demo.py            # Демо работы с Metadata и Scene
│   ├── indices_demo.py             # Демо спектральных индексов
│   └── gdal_bare_demo.py           # Пример использования GDAL без надстроек
├── 📁data
│   ├── 📁download                  # Скачанные фрагменты
│   └── 📁processed                 # Обработанные данные
├── .env.example                    # Пример переменных окружения
├── README.md                       # Документация
└── requirements.txt                # Зависимости (requests, python-dotenv)```
```

## Установка

### Требования

```requirements
requests>=2.28.0
python-dotenv>=1.0.0
```

**Примечание:** GDAL не требуется для работы библиотек `unisat_api` для доступа к данным в архивах `UNISAT`, но используется для работы инструментов обработки данных, реализованных на основе библиотек `processing`

Установка GDAL:

* Linux: `sudo apt install gdal-bin libgdal-dev python3-gdal`
* Windows: `OSGeo4W`

Также вы можете использовать Python из `QGIS`, если нужна встроенная поддержка `GDAL`

## Настройка

Создайте файл .env в корне проекта (указаны демонстрационные адреса):

```dotenv
METADATA_URL=<http://10.10.10.10:8085>
NGINX_URL=<http://10.10.10.10:8095>
```

## Импорт библиотек unisat_api

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

## Расширения для обработки данных `processing`

### GDALScene

Требует установки GDAL. Позволяет склеивать фрагменты сцены в один файл, обрезать по bbox и пересэмплировать

```python
from processing.gdal.scene import GDALScene

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
|resample_method    | str                        | Метод пересэмплинга: `nearest`, `bilinear`, `cubic` (по умолчанию `nearest`)

### Mask

Универсальный класс Mask позволяет загружать и применять маски из любых источников

```python
from processing.masks import Mask

# Загрузка маски из файла
mask = Mask.from_file("path/to/mask.tif")

# Загрузка из numpy массива
mask = Mask.from_array(binary_array)

# Комбинирование масок
combined = mask1 & mask2  # логическое И
combined = mask1 | mask2  # логическое ИЛИ
inverted = ~mask          # инверсия

# Применение маски к данным
masked_array = mask.apply_to_array(array)
mask.apply_to_file("input.tif", "output.tif")
```

### Спектральные индексы

```python
from processing.indices.sentinel2 import compute_ndvi, compute_evi, Sentinel2Indices
from processing.indices.base import SpectralIndex, compute_index

# Быстрый NDVI
result = compute_ndvi(scene, "ndvi_results")

# Пользовательский индекс
my_index = SpectralIndex(
    name="MY_INDEX",
    expression="(nir - red) / (nir + red + 0.1)",
    bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
    scale=10000
)
result = compute_index(scene, my_index, "custom_results")
```

### Маски для Sentinel-2 (SCL)

```python
from processing.masks.sentinel2 import get_scl_mask_for_scene, SCL_GOOD_CLASSES

# Создание маски из SCL
mask = get_scl_mask_for_scene(
    scene,
    good_classes=SCL_GOOD_CLASSES['vegetation_water'],
    dilate_clouds=2,
    dilate_shadows=3
)

# Применение маски к индексу
result = compute_ndvi(scene, "ndvi_clean", mask=mask)
```

#### Структура директорий для данных

Все данные сохраняются в data/:

```text
data/
├── download/          # Сырые фрагменты (scene.download)
│   └── my_download/
└── processed/         # Обработанные данные (GDALScene)
    └── ryazan_processed/
        ├── _params.json
        ├── _metadata.txt
        └── *.tif
```

#### Примечания

* BBOX указывается в градусах WGS84 (долгота, широта)
* GDALScene автоматически перепроецирует bbox в проекцию фрагментов
* Метаданные сохраняются в двух форматах:
* _params.json — полные параметры запроса и обработки
* _metadata.txt — CSV-подобный лог для всех сцен
* Пути к данным вычисляются относительно корня проекта
* Маски универсальны и могут быть созданы из любого источника (файл, массив, SCL)
