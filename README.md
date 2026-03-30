# Unisat Access

Библиотека для доступа к данным спутниковых архивов.

## Структура проекта
unisat_access/
├── unisat_api/ # Основная библиотека
│ ├── init.py
│ ├── config.py # Настройки (переменные окружения)
│ ├── parameters.py # Класс Parameters
│ ├── metadata.py # Класс Metadata
│ ├── scene.py # Класс Scene
│ ├── exceptions.py # Исключения
│ └── utils/
│ └── validators.py # Валидаторы
├── examples/ # Примеры использования
│ ├── test_parameters.py # Демо работы с Parameters
│ ├── test_metadata.py # Демо работы с Metadata
│ ├── ndvi_demo.py # Расчёт NDVI для сцены
│ ├── benchmark_read_methods.py # Сравнение методов чтения
│ └── check_gdal.py # Проверка GDAL
├── presets/ # JSON-файлы пресетов
├── tests/ # Юнит-тесты
│ └── test_parameters.py
├── data/ # Выходные данные (создаётся при запуске)
├── .env.example
├── requirements.txt
└── README.md

text

## Установка

### Linux/Unix

```bash
# Установка GDAL
sudo apt update
sudo apt install -y gdal-bin libgdal-dev python3-gdal

# Установка Python пакетов
pip install -r requirements.txt
Windows (QGIS Python)
bash
"C:\Program Files\QGIS 3.44.8\apps\Python312\python.exe" -m pip install -r requirements.txt
Настройка
Скопируйте .env.example в .env и отредактируйте:

env
METADATA_URL=http://192.168.80.137:8085
NGINX_URL=http://192.168.80.137:8095
PRESETS_DIR=./presets
METADATA_TIMEOUT=10
Основные классы
Parameters
Управление параметрами запроса. Загрузка/сохранение пресетов, валидация.

python
from unisat_api import Parameters

# Создание из пресета с переопределением
params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 10
})

# Методы
params.to_dict()                    # Словарь для запроса
params.save("my_preset")            # Сохранить новый пресет
params.get_required_params()        # Список обязательных параметров
params.get_parameters_description() # Описание всех параметров
Metadata
Получение метаданных. Итерация по сценам.

python
from unisat_api import Metadata

metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")

# Итерация
for scene in metadata:
    print(scene.dt, scene.satellite)

# Доступ по индексу
scene = metadata[0]
Scene
Работа со сценой: фрагменты, файлы, ссылки.

python
# Получение фрагментов (пути к файлам)
fragments = scene.get_products_info()
print(f"Фрагментов: {len(fragments)}")

# HTTP ссылки для GDAL
http_frag = scene.to_http(fragments[0])
for product, url in http_frag.items():
    print(f"{product}: {url}")

# vsicurl для GDAL (потоковое чтение)
vsicurl_frag = scene.to_vsicurl(fragments[0])
Примеры
test_parameters.py
Демонстрация работы с Parameters: загрузка пресета, переопределение параметров, валидация, сохранение.

bash
python examples/test_parameters.py
test_metadata.py
Демонстрация получения метаданных: поиск сцен, атрибуты, фрагменты, ссылки.

bash
python examples/test_metadata.py
ndvi_demo.py
Расчёт NDVI для сцены:

Загрузка красного (B4) и ближнего инфракрасного (B8) каналов

Объединение фрагментов

Сохранение в data/ndvi/

bash
python examples/ndvi_demo.py
benchmark_read_methods.py
Сравнение скорости чтения GeoTIFF разными методами:

/vsicurl/ — потоковое чтение через HTTP range

/vsimem/ — скачивание в память

Временный файл — скачивание на диск

bash
python examples/benchmark_read_methods.py
check_gdal.py
Проверка установки GDAL:

bash
python examples/check_gdal.py
Зависимости
requirements.txt
txt
requests>=2.28.0
numpy>=1.24.0
python-dotenv>=1.0.0
GDAL устанавливается отдельно:

Linux: sudo apt install gdal-bin libgdal-dev python3-gdal

Windows: через QGIS или OSGeo4W

Лицензия
MIT
"@ | Out-File -FilePath README.md -Encoding utf8