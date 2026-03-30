markdown
# Unisat API

Библиотека для доступа к данным спутниковых архивов.

## Структура проекта
unisat_access/
├── unisat_api/ # Основная библиотека
│ ├── init.py
│ ├── config.py # Настройки
│ ├── parameters.py # Работа с параметрами запросов
│ ├── metadata.py # Получение метаданных
│ ├── scene.py # Работа со сценами и фрагментами
│ ├── exceptions.py # Исключения
│ └── utils/ # Вспомогательные функции
│ └── validators.py
├── examples/ # Примеры использования
│ ├── ndvi_demo.py # Расчёт NDVI
│ ├── benchmark_read_methods.py # Сравнение методов чтения
│ ├── test_parameters.py # Демо работы с Parameters
│ ├── test_metadata.py # Демо работы с Metadata
│ └── check_gdal.py # Проверка GDAL
├── presets/ # JSON-файлы пресетов
├── tests/ # Тесты
│ └── test_parameters.py # Юнит-тесты
├── data/ # Выходные данные (создаётся при запуске)
├── .env # Переменные окружения (опционально)
├── requirements.txt # Зависимости
└── README.md

text

## Установка

### Linux/Unix

```bash
# Установка системных зависимостей (GDAL)
sudo apt update
sudo apt install -y gdal-bin libgdal-dev python3-gdal

# Установка Python пакетов
pip install -r requirements.txt
Windows (QGIS Python)
bash
"C:\Program Files\QGIS 3.44.8\apps\Python312\python.exe" -m pip install -r requirements.txt
Настройка
Создайте файл .env в корне проекта:

env
METADATA_URL=http://192.168.80.137:8085
NGINX_URL=http://192.168.80.137:8095
PRESETS_DIR=./presets
METADATA_TIMEOUT=10
Или задайте переменные окружения напрямую.

Быстрый старт
python
from unisat_api import Parameters, Metadata

# Создание параметров запроса
params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 10
})

# Получение метаданных
metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")

# Работа с первой сценой
scene = metadata[0]
print(f"Сцена: {scene.dt} | {scene.satellite}")

# Получение фрагментов
fragments = scene.get_fragments()
print(f"Фрагментов: {len(fragments)}")

# HTTP ссылки на файлы
http_frag = scene.to_http(fragments[0])
for product, url in http_frag.items():
    print(f"{product}: {url}")
Основные классы
Parameters
Управление параметрами запроса. Загрузка/сохранение пресетов, валидация параметров.

python
# Создание
params = Parameters("preset_name", {"param": "value"})

# Методы
params.to_dict()                    # Получить словарь
params.save("new_preset")           # Сохранить пресет
params.get_required_params()        # Список обязательных параметров
params.get_parameters_description() # Описание всех параметров
Metadata
Получение и хранение метаданных. Итерация по сценам.

python
metadata = Metadata(params)
for scene in metadata:
    print(scene.dt, scene.satellite)

scene = metadata[0]  # Доступ по индексу
Scene
Работа со сценой: фрагменты, файлы, ссылки.

python
fragments = scene.get_fragments()          # Пути к файлам
http_frag = scene.to_http(fragments[0])        # HTTP ссылки
vsicurl_frag = scene.to_vsicurl(fragments[0])  # vsicurl для GDAL
Примеры
test_parameters.py
Демонстрация работы с параметрами:

Загрузка пресета

Переопределение параметров

Валидация

Сохранение нового пресета

bash
python examples/test_parameters.py
test_metadata.py
Демонстрация получения метаданных:

Поиск сцен

Доступ к атрибутам сцены

Получение фрагментов и ссылок на файлы

bash
python examples/test_metadata.py
ndvi_demo.py
Расчёт NDVI для сцены:

Загрузка красного (B4) и ближнего инфракрасного (B8) каналов

Объединение фрагментов

Сохранение результата в data/ndvi/

bash
python examples/ndvi_demo.py
benchmark_read_methods.py
Сравнение скорости чтения GeoTIFF:

/vsicurl/ — потоковое чтение через HTTP range

/vsimem/ — скачивание в память

Временный файл — скачивание на диск

bash
python examples/benchmark_read_methods.py
check_gdal.py
Проверка установки GDAL и его версии:

bash
python examples/check_gdal.py
Зависимости
requirements.txt
text
requests>=2.28.0
numpy>=1.24.0
python-dotenv>=1.0.0
GDAL устанавливается отдельно:

Linux: sudo apt install gdal-bin libgdal-dev python3-gdal

Windows: через QGIS или OSGeo4W

Лицензия
MIT