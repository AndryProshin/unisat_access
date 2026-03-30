# benchmark_read_methods.py
# Сравнение скорости чтения GeoTIFF разными методами

from parameters import Parameters
from metadata import Metadata
import numpy as np
from osgeo import gdal
import requests
import tempfile
import time
from pathlib import Path

gdal.UseExceptions()

# Настройка
params = Parameters("sentinel2_boa_ndvi", {})
metadata = Metadata(params)
scene = metadata[3]

fragments = scene.get_fragments()
http_frag = scene.to_http(fragments[0])

red_url = http_frag.get("channel4_l2a")

print("=" * 80)
print("СРАВНЕНИЕ МЕТОДОВ ЧТЕНИЯ GeoTIFF")
print("=" * 80)
print(f"Тестовый файл: {red_url[:80]}...")
print("=" * 80)

# ============================================
# МЕТОД 1: /vsicurl/
# ============================================
def read_vsicurl(url):
    total_start = time.time()
    ds = gdal.Open(f"/vsicurl/{url}")
    if ds is None:
        return None, 0, 0
    gdal_open_time = time.time() - total_start
    band = ds.GetRasterBand(1)
    read_start = time.time()
    arr = band.ReadAsArray()
    read_time = time.time() - read_start
    shape = arr.shape
    size_mb = arr.nbytes / (1024 * 1024)
    ds = None
    total_time = time.time() - total_start
    return arr, total_time, read_time, gdal_open_time, shape, size_mb

# ============================================
# МЕТОД 2: Прямой HTTP через GDAL
# ============================================
def read_http_direct(url):
    total_start = time.time()
    ds = gdal.Open(url)
    if ds is None:
        return None, 0, 0
    gdal_open_time = time.time() - total_start
    band = ds.GetRasterBand(1)
    read_start = time.time()
    arr = band.ReadAsArray()
    read_time = time.time() - read_start
    shape = arr.shape
    size_mb = arr.nbytes / (1024 * 1024)
    ds = None
    total_time = time.time() - total_start
    return arr, total_time, read_time, gdal_open_time, shape, size_mb

# ============================================
# МЕТОД 3: /vsimem/
# ============================================
def read_vsimem(url):
    total_start = time.time()
    download_start = time.time()
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    download_time = time.time() - download_start
    gdal.FileFromMemBuffer('/vsimem/temp.tif', response.content)
    open_start = time.time()
    ds = gdal.Open('/vsimem/temp.tif')
    if ds is None:
        gdal.Unlink('/vsimem/temp.tif')
        return None, 0, 0
    open_time = time.time() - open_start
    band = ds.GetRasterBand(1)
    read_start = time.time()
    arr = band.ReadAsArray()
    read_time = time.time() - read_start
    shape = arr.shape
    size_mb = arr.nbytes / (1024 * 1024)
    ds = None
    gdal.Unlink('/vsimem/temp.tif')
    total_time = time.time() - total_start
    return arr, total_time, read_time, download_time, open_time, shape, size_mb

# ============================================
# МЕТОД 4: Временный файл
# ============================================
def read_temp_file(url):
    total_start = time.time()
    download_start = time.time()
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp:
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name
    download_time = time.time() - download_start
    open_start = time.time()
    ds = gdal.Open(tmp_path)
    if ds is None:
        Path(tmp_path).unlink()
        return None, 0, 0
    open_time = time.time() - open_start
    band = ds.GetRasterBand(1)
    read_start = time.time()
    arr = band.ReadAsArray()
    read_time = time.time() - read_start
    shape = arr.shape
    size_mb = arr.nbytes / (1024 * 1024)
    ds = None
    Path(tmp_path).unlink()
    total_time = time.time() - total_start
    return arr, total_time, read_time, download_time, open_time, shape, size_mb

# ============================================
# МЕТОД 5: Прямое скачивание
# ============================================
def read_direct_download(url):
    start = time.time()
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    size_mb = len(response.content) / (1024 * 1024)
    elapsed = time.time() - start
    return elapsed, size_mb

# ============================================
# ЗАПУСК ТЕСТОВ
# ============================================

print("\nПолучение информации о файле...")
ds_test = gdal.Open(f"/vsicurl/{red_url}")
if ds_test:
    cols = ds_test.RasterXSize
    rows = ds_test.RasterYSize
    bands = ds_test.RasterCount
    print(f"  Размер: {rows} x {cols} пикселей")
    print(f"  Каналов: {bands}")
    ds_test = None

print("\n" + "=" * 80)
print("ДЕТАЛЬНЫЕ ЗАМЕРЫ")
print("=" * 80)

results = {}

# Метод 1
print("\n1. /vsicurl/ (GDAL потоковое чтение через HTTP range)...")
try:
    arr1, total1, read1, open1, shape1, size1 = read_vsicurl(red_url)
    if arr1 is not None:
        results['/vsicurl/'] = {'total': total1, 'read': read1, 'open': open1}
        print(f"   GDAL открытие: {open1:.2f} сек")
        print(f"   GDAL чтение:   {read1:.2f} сек")
        print(f"   ИТОГО:         {total1:.2f} сек")
        print(f"   Размер данных: {size1:.1f} MB")
        print(f"   Размерность:   {shape1}")
    else:
        print("   Ошибка")
except Exception as e:
    print(f"   Ошибка: {e}")

# Метод 2
print("\n2. Прямой HTTP (GDAL открывает HTTP URL напрямую)...")
try:
    arr2, total2, read2, open2, shape2, size2 = read_http_direct(red_url)
    if arr2 is not None:
        results['Прямой HTTP (GDAL)'] = {'total': total2, 'read': read2, 'open': open2}
        print(f"   GDAL открытие: {open2:.2f} сек")
        print(f"   GDAL чтение:   {read2:.2f} сек")
        print(f"   ИТОГО:         {total2:.2f} сек")
        print(f"   Размер данных: {size2:.1f} MB")
        print(f"   Размерность:   {shape2}")
    else:
        print("   Ошибка")
except Exception as e:
    print(f"   Ошибка: {e}")

# Метод 3
print("\n3. /vsimem/ (скачивание в память + GDAL)...")
try:
    arr3, total3, read3, download3, open3, shape3, size3 = read_vsimem(red_url)
    if arr3 is not None:
        results['/vsimem/'] = {'total': total3, 'read': read3, 'download': download3, 'open': open3}
        print(f"   Скачивание:    {download3:.2f} сек")
        print(f"   GDAL открытие: {open3:.2f} сек")
        print(f"   GDAL чтение:   {read3:.2f} сек")
        print(f"   ИТОГО:         {total3:.2f} сек")
        print(f"   Размер данных: {size3:.1f} MB")
        print(f"   Размерность:   {shape3}")
    else:
        print("   Ошибка")
except Exception as e:
    print(f"   Ошибка: {e}")

# Метод 4
print("\n4. Временный файл (скачивание на диск + GDAL)...")
try:
    arr4, total4, read4, download4, open4, shape4, size4 = read_temp_file(red_url)
    if arr4 is not None:
        results['Временный файл'] = {'total': total4, 'read': read4, 'download': download4, 'open': open4}
        print(f"   Скачивание:    {download4:.2f} сек")
        print(f"   GDAL открытие: {open4:.2f} сек")
        print(f"   GDAL чтение:   {read4:.2f} сек")
        print(f"   ИТОГО:         {total4:.2f} сек")
        print(f"   Размер данных: {size4:.1f} MB")
        print(f"   Размерность:   {shape4}")
    else:
        print("   Ошибка")
except Exception as e:
    print(f"   Ошибка: {e}")

# Метод 5
print("\n5. Прямое скачивание (только HTTP, эталон)...")
try:
    time5, size5 = read_direct_download(red_url)
    results['Прямое скачивание'] = {'total': time5, 'size': size5}
    print(f"   Скачивание:    {time5:.2f} сек")
    print(f"   Размер файла:  {size5:.1f} MB")
except Exception as e:
    print(f"   Ошибка: {e}")

# ============================================
# ИТОГОВАЯ ТАБЛИЦА
# ============================================

print("\n" + "=" * 80)
print("ИТОГОВАЯ ТАБЛИЦА СРАВНЕНИЯ")
print("=" * 80)

print("\nМетод                          Скачивание   GDAL       GDAL       ИТОГО")
print("                               (сек)        открытие   чтение     (сек)")
print("-" * 80)

if '/vsicurl/' in results:
    r = results['/vsicurl/']
    print(f"/vsicurl/                        N/A          {r['open']:6.2f}     {r['read']:6.2f}     {r['total']:6.2f}")

if 'Прямой HTTP (GDAL)' in results:
    r = results['Прямой HTTP (GDAL)']
    print(f"Прямой HTTP (GDAL)               N/A          {r['open']:6.2f}     {r['read']:6.2f}     {r['total']:6.2f}")

if '/vsimem/' in results:
    r = results['/vsimem/']
    print(f"/vsimem/ (память)                {r['download']:6.2f}     {r['open']:6.2f}     {r['read']:6.2f}     {r['total']:6.2f}")

if 'Временный файл' in results:
    r = results['Временный файл']
    print(f"Временный файл (диск)            {r['download']:6.2f}     {r['open']:6.2f}     {r['read']:6.2f}     {r['total']:6.2f}")

if 'Прямое скачивание' in results:
    r = results['Прямое скачивание']
    print(f"Прямое скачивание (эталон)       {r['total']:6.2f}     N/A        N/A        {r['total']:6.2f}")

print("-" * 80)

print("\n=== Завершено ===")