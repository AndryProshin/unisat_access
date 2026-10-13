import os
import sys
from pathlib import Path
import numpy as np
from osgeo import gdal, osr
from dotenv import load_dotenv

def main():
    # Включаем генерацию исключений Python при ошибках в GDAL
    gdal.UseExceptions()
    
    # 1. Загрузка конфигурации из .env
    load_dotenv(Path(__file__).parent / ".env")
    
    bucket = os.getenv("S3TOOL_BUCKET")
    access = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint = os.getenv("AWS_ENDPOINT_URL")  # Например: http://192.168.20.59:80
    
    if not all([bucket, access, secret, endpoint]):
        print("ERROR: Проверьте переменные окружения в .env")
        sys.exit(1)
        
    # 2. Очистка Endpoint (удаляем протокол http:// или https://)
    cleaned_endpoint = endpoint
    if "://" in cleaned_endpoint:
        cleaned_endpoint = cleaned_endpoint.split("://", 1)[1]
    cleaned_endpoint = cleaned_endpoint.rstrip("/")
    
    # Извлекаем "голый" IP-адрес без порта (на случай, если порт был указан через двоеточие)
    ip_only = cleaned_endpoint.split(":")[0]
    
    # Формируем классический путь внутри виртуальной файловой системы GDAL /vsis3/
    key = "gdal_direct_final.tif"
    vsi_path = f"/vsis3/{bucket}/{key}"
    
    print(f"Подключение к бакету '{bucket}' по адресу {cleaned_endpoint}...")

    # 3. Базовые настройки авторизации S3
    gdal.SetConfigOption("AWS_ACCESS_KEY_ID", access)
    gdal.SetConfigOption("AWS_SECRET_ACCESS_KEY", secret)
    gdal.SetConfigOption("AWS_S3_ENDPOINT", cleaned_endpoint)
    gdal.SetConfigOption("AWS_HTTPS", "YES" if endpoint.startswith("https") else "NO")
    gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE")  # Используем path-style (host/bucket/key)

    # =========================================================================
    # РАЗВЕРНУТОЕ ОПИСАНИЕ КЛЮЧЕВОГО ИЗМЕНЕНИЯ (ФИКС ОШИБКИ SIGNATURE MISMATCH)
    # =========================================================================
    # СУТЬ ПРОБЛЕМЫ: 
    # Когда GDAL генерирует цифровую подпись AWS v4, он берет эндпоинт вместе с 
    # портом (например, '192.168.20.59:80'), строит на его основе криптографический 
    # хэш и вставляет его в заголовок Authorization. 
    # Однако следом за этим сетевой движок (libcurl) видит, что порт 80 является 
    # стандартным дефолтным портом для протокола HTTP, и при физической отправке 
    # пакета автоматически вырезает его, отправляя заголовок "Host: 192.168.20.59".
    #
    # Когда пакет прилетает в Ceph Squid, сервер берет фактически пришедший заголовок 
    # Host (БЕЗ порта), считает подпись на своей стороне и сравнивает её с подписью 
    # GDAL (которая была посчитана С портом). Из-за расхождения в три символа (:80) 
    # контрольные суммы не совпадают, и Ceph возвращает 403 SignatureDoesNotMatch.
    #
    # РЕШЕНИЕ:
    # Мы используем низкоуровневую опцию "GDAL_HTTP_HEADERS". Это силовой хук для 
    # библиотеки libcurl. Он срабатывает в самый последний момент перед отправкой 
    # пакета в сетевую карту — уже после того, как все внутренние правила curl отрезали 
    # порт. Этот хук насильно внедряет порт обратно в HTTP-заголовок Host.
    # В результате и GDAL считает подпись с портом, и в сеть уходит заголовок с портом. 
    # На стороне Ceph алгоритмы проверок сходятся байт в байт.
    # =========================================================================
    gdal.SetConfigOption("GDAL_HTTP_HEADERS", f"Host: {ip_only}:80")
    
    # Требование Ceph Squid для PUT-запросов (подписывать хэш тела файла)
    gdal.SetConfigOption("AWS_REQUEST_PAYLOAD_SIGNED", "YES")
    gdal.SetConfigOption("GDAL_HTTP_VERSION", "1.1")
    gdal.SetConfigOption("CPL_VSIL_USE_TEMP_FILE_FOR_RANDOM_WRITE", "YES")
    
    # Выключаем отладочные логи, так как транспорт теперь работает стабильно
    gdal.SetConfigOption("CPL_DEBUG", "OFF")
    gdal.SetConfigOption("CPL_CURL_VERBOSE", "OFF")

    # 4. ТЕСТ ЗАПИСИ
    print("-> Запись тестового GeoTIFF напрямую в Ceph S3...")
    try:
        drv = gdal.GetDriverByName("GTiff")
        ds = drv.Create(vsi_path, 4, 4, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"])
        ds.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, -1.0))
        
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        ds.SetProjection(srs.ExportToWkt())
        
        arr = np.arange(16, dtype=np.float32).reshape(4, 4)
        ds.GetRasterBand(1).WriteArray(arr)
        ds = None  # Закрываем датасет, инициируя физический PUT-запрос в Ceph
        print("   ЗАПИСЬ ВЫПОЛНЕНА УСПЕШНО!")
    except Exception as e:
        print(f"   ОШИБКА ЗАПИСИ: {e}")
        return

    # 5. ТЕСТ ЧТЕНИЯ
    print("-> Чтение созданного файла обратно из Ceph S3...")
    try:
        ds_read = gdal.Open(vsi_path)
        read_arr = ds_read.GetRasterBand(1).ReadAsArray()
        ds_read = None
        
        if np.array_equal(arr, read_arr):
            print("   ЧТЕНИЕ ВЫПОЛНЕНА УСПЕШНО! Данные валидны.")
    except Exception as e:
        print(f"   ОШИБКА ЧТЕНИЯ: {e}")

if __name__ == "__main__":
    main()
