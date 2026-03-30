# Unisat Access

Библиотека для организации пользовательского доступа к данным спутниковых архивов, реализованных по технологии UNISAT.

## Структура проекта
* unisat_access/  
	* unisat_api/ # Основная библиотека  
        * __init__.py  
        * config.py # Настройки (переменные окружения)
        * parameters.py # Класс Parameters
        * metadata.py # Класс Metadata
        * scene.py # Класс Scene
        * exceptions.py # Исключения
        * .env.example
        * utils/
            * validators.py # Валидаторы
    * examples/ # Примеры использования
        * test_parameters.py # Демо работы с классом Parameters
        * test_metadata.py # Демо работы с классами Metadata и Scene
        * ndvi_demo.py # Расчёт и склейка NDVI по сценам, полученным в результате запроса
        * benchmark_read_methods.py # Сравнение методов чтения geotif файлов
        * check_gdal.py # Проверка поддрежки GDAL
    * presets/ # JSON-файлы пресетов
    * tests/ # Юнит-тесты
  		* test_parameters.py
    * example.py # Простейший пример для ознакомления
    * data/ # Выходные данные (создаётся при запуске)
    * requirements.txt
    * README.md


## Установка

### Linux/Unix

```bash
sudo apt update
sudo apt install -y gdal-bin libgdal-dev python3-gdal
pip install -r requirements.txt
Windows (QGIS Python)
bash
"C:\Program Files\QGIS 3.44.8\apps\Python312\python.exe" -m pip install -r requirements.txt
Настройка
Создайте файл .env в корне проекта:

env
METADATA_URL=http://10.10.10.10:8085
NGINX_URL=http://10.10.10.10:8095
PRESETS_DIR=./presets
METADATA_TIMEOUT=10
```

## Основные классы
# Parameters
```Управление параметрами запроса. Загрузка/сохранение пресетов, валидация.

python
from unisat_api import Parameters

params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 10
})

params.to_dict()                    # Словарь для запроса
params.save("my_preset")            # Сохранить новый пресет
params.get_required_params()        # Список обязательных параметров
params.get_parameters_description() # Описание всех параметров
```

# Metadata
```Получение метаданных. Итерация по сценам.

python
from unisat_api import Metadata

metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")

for scene in metadata:
    print(scene.dt, scene.satellite)

scene = metadata[0]
```

# Scene
```Работа со сценой: фрагменты, файлы, ссылки.

python
fragments = scene.get_fragments()
http_frag = scene.to_http(fragments[0])
vsicurl_frag = scene.to_vsicurl(fragments[0])
```

# Зависимости
requirements.txt:

requests>=2.28.0
numpy>=1.24.0
python-dotenv>=1.0.0
GDAL устанавливается отдешно:

Linux: sudo apt install gdal-bin libgdal-dev python3-gdal

Windows: через QGIS или OSGeo4W

Лицензия
MIT
