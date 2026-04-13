# ndvi_demo.py
# Демонстрация работы с NDVI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata
from unisat_api.extras.gdal_scene import GDALScene

import numpy as np
from osgeo import gdal

gdal.UseExceptions()


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def compute_ndvi(red, nir):
    """Вычисление NDVI из массивов numpy"""
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

def main():
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

    # 3. Подготовка директории для сохранения (data/processed/ndvi)
    output_dir = Path("data/processed/ndvi")
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    for scene_idx, scene in enumerate(metadata):
        print(f"\n{'=' * 60}")
        print(f"Сцена {scene_idx + 1}/{len(metadata)}: {scene.dt} | {scene.satellite} | {scene.device}")
        print('=' * 60)
        
        try:
            # Используем GDALScene для склейки и обрезки
            gdal_scene = GDALScene(scene)
            
            # Сохраняем RED (channel4) и NIR (channel8) каналы
            result = gdal_scene.save_products(
                result_subdir="ndvi_temp",  # временная поддиректория
                products=["channel4_l2a", "channel8_l2a"],
                resample_to="highest",
                resample_method="bilinear"
            )
            
            # Пути к сохранённым файлам
            red_path = result["files"].get("channel4_l2a")
            nir_path = result["files"].get("channel8_l2a")
            
            if not red_path or not nir_path:
                print(f"✗ Не удалось получить каналы")
                fail_count += 1
                continue
            
            # Открываем полученные GeoTIFF
            print(f"\n--- Открытие обработанных каналов ---")
            
            red_ds = gdal.Open(red_path)
            nir_ds = gdal.Open(nir_path)
            
            red_band = red_ds.GetRasterBand(1)
            nir_band = nir_ds.GetRasterBand(1)
            
            red = red_band.ReadAsArray().astype(np.float32)
            nir = nir_band.ReadAsArray().astype(np.float32)
            
            # Нормализация (Sentinel-2 BOA имеет масштаб 10000)
            if red.max() > 1:
                red = red / 10000.0
            if nir.max() > 1:
                nir = nir / 10000.0
            
            transform = red_ds.GetGeoTransform()
            proj = red_ds.GetProjection()
            
            red_ds = None
            nir_ds = None
            
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

    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Всего сцен: {len(metadata)}")
    print(f"Успешно обработано: {success_count}")
    print(f"С ошибками: {fail_count}")
    print(f"Результаты сохранены в: {output_dir.absolute()}")
    print("\n=== Завершено ===")


if __name__ == "__main__":
    main()