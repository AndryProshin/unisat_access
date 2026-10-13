import os
import sys
from pathlib import Path
import numpy as np
from osgeo import gdal, osr
from dotenv import load_dotenv

def main():
    gdal.UseExceptions()
    
    # 1. Загрузка параметров из .env (Обычный IP: http://192.168.20.59:80)
    load_dotenv(Path(__file__).parent / ".env")
    
    bucket = os.getenv("S3TOOL_BUCKET")
    access = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    
    if not all([bucket, access, secret, endpoint]):
        print("Ошибка: Проверьте переменные в .env")
        sys.exit(1)
        
    # 2. Извлекаем чистый IP
    cleaned_endpoint = endpoint
    if "://" in cleaned_endpoint:
        cleaned_endpoint = cleaned_endpoint.split("://", 1)[1]
    cleaned_endpoint = cleaned_endpoint.rstrip("/")
    
    # Убираем порт, если он есть, для чистой конфигурации
    ip_only = cleaned_endpoint.split(":")[0]
    
    # 3. Путь VSI
    key = "gdal_final_fixed.tif"
    vsi_path = f"/vsis3/{bucket}/{key}"
    
    print(f"Bucket:   {bucket}")
    print(f"IP Ceph:  {ip_only}")
    print(f"VSI Path: {vsi_path}\n")

    # 4. Конфигурация авторизации
    gdal.SetConfigOption("AWS_ACCESS_KEY_ID", access)
    gdal.SetConfigOption("AWS_SECRET_ACCESS_KEY", secret)
    
    # ТРЮК: Говорим GDAL слать запросы на IP, но...
    gdal.SetConfigOption("AWS_S3_ENDPOINT", cleaned_endpoint)
    gdal.SetConfigOption("AWS_HTTPS", "YES" if endpoint.startswith("https") else "NO")
    gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE") 
    
    # Привязываем регион к us-east-1 (дефолт для Ceph по IP)
    gdal.SetConfigOption("AWS_DEFAULT_REGION", "us-east-1")
    gdal.SetConfigOption("AWS_REGION", "us-east-1")
    
    # ЖЕСТКИЙ ХАК ЗАГОЛОВКА ДЛЯ БАЛАНСИРОВЩИКА CEPH:
    # Мы принудительно заставляем curl отправлять Host со значением IP.
    # Это перекрывает внутренний баг GDAL с отрезанием портов.
    gdal.SetConfigOption("GDAL_HTTP_HEADERS", f"Host: {ip_only}")
    
    gdal.SetConfigOption("AWS_REQUEST_PAYLOAD_SIGNED", "YES")
    gdal.SetConfigOption("GDAL_HTTP_VERSION", "1.1")
    gdal.SetConfigOption("CPL_VSIL_USE_TEMP_FILE_FOR_RANDOM_WRITE", "YES")
    
    # Логи
    gdal.SetConfigOption("CPL_DEBUG", "ON")
    gdal.SetConfigOption("CPL_CURL_VERBOSE", "ON")

    # 5. ЗАПИСЬ
    print("Запись файла...")
    try:
        drv = gdal.GetDriverByName("GTiff")
        ds = drv.Create(vsi_path, 4, 4, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"])
        ds.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, -1.0))
        
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        ds.SetProjection(srs.ExportToWkt())
        
        arr = np.arange(16, dtype=np.float32).reshape(4, 4)
        ds.GetRasterBand(1).WriteArray(arr)
        ds = None  
        print("  -> ЗАПИСЬ: УСПЕШНО")
        
    except Exception as e:
        print(f"  -> ЗАПИСЬ: ОШИБКА: {e}")
        return

    # 6. ЧТЕНИЕ
    print("\nЧтение файла...")
    try:
        ds_read = gdal.Open(vsi_path)
        read_arr = ds_read.GetRasterBand(1).ReadAsArray()
        ds_read = None
        
        if np.array_equal(arr, read_arr):
            print("  -> ЧТЕНИЕ: УСПЕШНО! Проблема решена программно.")
    except Exception as e:
        print(f"  -> ЧТЕНИЕ: ОШИБКА: {e}")

if __name__ == "__main__":
    main()
