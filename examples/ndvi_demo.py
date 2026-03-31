# ndvi_demo.py
# Демонстрация работы с NDVI в JupyterLab

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

import numpy as np
from osgeo import gdal

gdal.UseExceptions()



# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def read_geotiff(url, desc):
    """Чтение GeoTIFF по HTTP (прямое открытие)"""
    print(f"  Чтение: {desc} -> {url[:80]}...")
    ds = gdal.Open(url)  # ← прямой HTTP, без /vsicurl/
    if ds is None:
        print(f"    Ошибка: не удалось открыть")
        return None, None, None
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(np.float32)
    if arr.max() > 1:
        arr = arr / 10000.0
    transform = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None
    print(f"    Размер: {arr.shape}")
    return arr, transform, proj


def merge_fragments(arrays, names):
    """Объединяет массивы фрагментов"""
    if len(arrays) == 1:
        print(f"  Склейка: только один фрагмент, объединение не требуется")
        return arrays[0]
    
    print(f"  Склейка: объединяем {len(arrays)} фрагментов")
    max_h = max(arr.shape[0] for arr in arrays)
    max_w = max(arr.shape[1] for arr in arrays)
    print(f"    Результирующий размер: {max_h} x {max_w}")
    
    result = np.zeros((max_h, max_w), dtype=np.float32)
    for i, arr in enumerate(arrays):
        h, w = arr.shape
        print(f"    Фрагмент {names[i]}: размер {h} x {w} -> вставка в верхний левый угол")
        result[:h, :w] = np.maximum(result[:h, :w], arr)
    
    return result


def compute_ndvi(red, nir):
    """Вычисление NDVI"""
    print("  Вычисление NDVI...")
    denom = nir + red
    mask = denom == 0
    ndvi = np.zeros_like(red)
    with np.errstate(divide='ignore', invalid='ignore'):
        ndvi = (nir - red) / denom
        ndvi[mask] = -9999
    print(f"    Диапазон NDVI: {ndvi.min():.3f} .. {ndvi.max():.3f}")
    return ndvi


def save_geotiff(arr, path, transform, proj):
    """Сохранение GeoTIFF со сжатием"""
    print(f"  Сохранение: {path}")
    
    driver = gdal.GetDriverByName('GTiff')
    options = [
        'COMPRESS=DEFLATE',
        'PREDICTOR=3',
        'TILED=YES',
        'BLOCKXSIZE=512',
        'BLOCKYSIZE=512',
        'BIGTIFF=IF_SAFER'
    ]
    
    ds = driver.Create(str(path), arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32, options=options)
    ds.SetGeoTransform(transform)
    ds.SetProjection(proj)
    
    band = ds.GetRasterBand(1)
    band.WriteArray(arr)
    band.SetNoDataValue(-9999)
    band.SetStatistics(
        float(np.nanmin(arr)),
        float(np.nanmax(arr)),
        float(np.nanmean(arr)),
        float(np.nanstd(arr))
    )
    
    ds = None


# ============================================
# ОСНОВНАЯ ЛОГИКА
# ============================================

# 1. Настройка параметров запроса
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-08-01 00:00:00",
    "dt": "2024-08-10 00:00:00",
    "products": ["channel8_l2a", "channel4_l2a"],
    "bbox": [44.5, 44.5, 45, 45],
    "limit": 10,
})

# 2. Загрузка метаданных
metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")
print("=" * 60)

# 3. Подготовка директории для сохранения
output_dir = Path("data/ndvi")
output_dir.mkdir(parents=True, exist_ok=True)

# 4. Цикл по всем сценам
success_count = 0
fail_count = 0

for scene_idx, scene in enumerate(metadata):
    print(f"\n{'=' * 60}")
    print(f"Сцена {scene_idx + 1}/{len(metadata)}: {scene.dt} | {scene.satellite} | {scene.device}")
    print('=' * 60)
    
    # Получение фрагментов
    fragments = scene.get_fragments()
    print(f"Фрагментов: {len(fragments)}")
    
    # Массивы для хранения фрагментов
    red_arrays = []
    nir_arrays = []
    fragment_names = []
    transform = None
    proj = None
    
    # Обработка фрагментов сцены
    print("\n--- Обработка фрагментов ---")
    for i, frag in enumerate(fragments):
        print(f"\nФрагмент {i}:")
        fragment_names.append(str(i))
        
        # Получаем HTTP ссылки
        http_frag = scene.to_http(frag)
        
        red_url = http_frag.get("channel4_l2a")   # B4
        nir_url = http_frag.get("channel8_l2a")   # B8
        
        if not red_url or not nir_url:
            print("  Пропуск: отсутствуют каналы")
            continue
        
        # Читаем RED канал напрямую по HTTP
        red, t, p = read_geotiff(red_url, f"RED (B4) фрагмент {i}")
        if red is None:
            continue
        
        # Читаем NIR канал напрямую по HTTP
        nir, _, _ = read_geotiff(nir_url, f"NIR (B8) фрагмент {i}")
        if nir is None:
            continue
        
        red_arrays.append(red)
        nir_arrays.append(nir)
        
        if transform is None:
            transform, proj = t, p
    
    # Объединение фрагментов и вычисление NDVI
    print("\n--- Объединение фрагментов ---")
    if red_arrays and nir_arrays:
        try:
            # Объединяем фрагменты
            print(f"\nRED канал:")
            red = merge_fragments(red_arrays, fragment_names)
            
            print(f"\nNIR канал:")
            nir = merge_fragments(nir_arrays, fragment_names)
            
            # Вычисляем NDVI
            print("\n--- Вычисление NDVI ---")
            ndvi = compute_ndvi(red, nir)
            
            # Формируем имя файла: YYYYMMDD_hhmmss_ndvi.tif
            dt_str = scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
            out_path = output_dir / f"{dt_str}_ndvi.tif"
            
            # Сохраняем
            print("\n--- Сохранение ---")
            save_geotiff(ndvi, out_path, transform, proj)
            print(f"\n✓ Успешно сохранено: {out_path}")
            success_count += 1
            
        except Exception as e:
            print(f"\n✗ Ошибка при обработке сцены {scene_idx + 1}: {e}")
            fail_count += 1
    else:
        print("\n✗ Не удалось загрузить ни одного фрагмента")
        fail_count += 1

# Итоговая статистика
print("\n" + "=" * 60)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 60)
print(f"Всего сцен: {len(metadata)}")
print(f"Успешно обработано: {success_count}")
print(f"С ошибками: {fail_count}")
print(f"Результаты сохранены в: {output_dir.absolute()}")
print("\n=== Завершено ===")