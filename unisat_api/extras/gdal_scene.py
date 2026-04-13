"""
GDAL расширение для Scene
Требует: pip install gdal
"""

import json
import csv
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from osgeo import gdal, osr, ogr

from ..scene import Scene
from .. import config


class GDALScene:
    """Обёртка для Scene с GDAL функционалом"""
    
    def __init__(self, scene: Scene):
        self._scene = scene
        gdal.UseExceptions()
    
    @property
    def original(self) -> Scene:
        """Доступ к оригинальной сцене"""
        return self._scene

    def save_products(
        self,
        result_subdir: str,
        products: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[Union[str, float]] = None,
        resample_method: str = "nearest"
    ) -> Dict[str, Any]:
        """
        Склеить фрагменты по продуктам, обрезать по bbox и сохранить как GeoTIFF.
        
        Args:
            result_subdir: имя поддиректории внутри data/processed/ (обязательный параметр)
            products: список продуктов (None → все продукты сцены)
            bbox: [minx, miny, maxx, maxy] в WGS84 (None → из параметров сцены)
            resample_to: пересэмплирование (None, "highest", "lowest", или число в метрах)
            resample_method: метод пересэмплинга ("nearest", "bilinear", "cubic")
        
        Returns:
            словарь с output_dir и files {product: full_path}
        """
        # Определяем выходную директорию (абсолютный путь)
        output_path = config.PROCESSED_DIR / result_subdir
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Определяем продукты
        if products is None:
            products = list(self._scene.products.keys())
        
        # Определяем bbox (в WGS84)
        if bbox is None:
            bbox = self._scene._params.get("bbox")
            if bbox is None:
                raise ValueError("bbox не указан ни в параметрах сцены, ни в аргументах")
        
        print(f"\n=== Диагностика ===")
        print(f"Сцена: {self._scene.dt}")
        print(f"Исходный bbox (WGS84): {bbox}")
        
        # Получаем фрагменты
        fragments = self._scene.get_fragments()
        if not fragments:
            raise ValueError("Нет фрагментов для обработки")
        
        print(f"Количество фрагментов: {len(fragments)}")
        
        # Для каждого продукта: склеить и обрезать
        saved_files = {}
        for product in products:
            filename = self._process_product(
                product, fragments, bbox, output_path,
                resample_to, resample_method
            )
            if filename:
                saved_files[product] = str(output_path / filename)
        
        # Сохраняем метаданные
        self._save_metadata(output_path, products, bbox, resample_to, resample_method)
        
        print(f"\nСохранено в: {output_path}")
        
        return {
            "output_dir": str(output_path),
            "files": saved_files
        }


    def _bbox_to_cutline(self, bbox_wgs84: List[float]) -> str:
        """
        Преобразовать bbox в GeoJSON файл для использования в gdal.Warp.
        
        Args:
            bbox_wgs84: [minx, miny, maxx, maxy] в WGS84
        
        Returns:
            путь к временному GeoJSON файлу
        """
        # Создаём полигон из bbox
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[1])
        ring.AddPoint(bbox_wgs84[2], bbox_wgs84[1])
        ring.AddPoint(bbox_wgs84[2], bbox_wgs84[3])
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[3])
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[1])
        
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": json.loads(poly.ExportToJson()),
                    "properties": {}
                }]
            }
            json.dump(geojson, f)
            return f.name
    
    def _process_product(
        self,
        product: str,
        fragments: List[Dict],
        bbox_wgs84: List[float],
        output_path: Path,
        resample_to: Optional[Union[str, float]],
        resample_method: str
    ) -> Optional[str]:
        """Обработать один продукт: склеить фрагменты и обрезать по bbox"""
        
        print(f"\n--- Обработка продукта: {product} ---")
        
        # Собираем все HTTP пути для этого продукта
        http_paths = []
        for i, frag in enumerate(fragments):
            if product in frag:
                path = frag[product]
                http_paths.append(f"{config.NGINX_BASE_URL}/{path}")
                print(f"  Фрагмент {i}: {path}")
        
        if not http_paths:
            print(f"Предупреждение: продукт {product} не найден во фрагментах")
            return None
        
        print(f"Всего фрагментов для продукта: {len(http_paths)}")
        
        # Создаём VRT из всех фрагментов
        print(f"\nСоздание VRT для {product}...")
        vrt_path = f"/vsimem/{product}_merge.vrt"
        gdal.BuildVRT(vrt_path, http_paths)
        
        # Формируем имя выходного файла
        dt_str = self._scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        output_file = output_path / f"{dt_str}_{product}.tif"
        
        # Создаём cutline из bbox
        cutline_path = self._bbox_to_cutline(bbox_wgs84)
        
        # Параметры Warp
        warp_options = {
            'format': 'GTiff',
            'cutlineDSName': cutline_path,
            'cropToCutline': True,
            'dstNodata': 0,
            'creationOptions': ["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"]
        }
        
        # Добавляем пересэмплирование если нужно
        if resample_to is not None:
            # Определяем целевое разрешение
            src_ds = gdal.Open(vrt_path)
            geo = src_ds.GetGeoTransform()
            src_res = abs(geo[1])
            src_ds = None
            
            if resample_to == "highest":
                target_res = src_res  # сохраняем текущее разрешение
            elif resample_to == "lowest":
                # Для lowest нужно знать разрешение других продуктов
                # Пока оставляем как есть
                target_res = src_res
            elif isinstance(resample_to, (int, float)):
                target_res = resample_to
            else:
                target_res = src_res
            
            # Вычисляем новые размеры
            if target_res != src_res:
                scale = src_res / target_res
                warp_options['xRes'] = target_res
                warp_options['yRes'] = target_res
                warp_options['resampleAlg'] = self._get_resample_alg(resample_method)
        
        # Выполняем Warp с обрезкой
        print(f"Обрезка по bbox и сохранение в {output_file.name}...")
        gdal.Warp(str(output_file), vrt_path, **warp_options)
        
        # Проверяем размер созданного файла
        file_size = output_file.stat().st_size
        print(f"Размер файла: {file_size} байт ({file_size / 1024 / 1024:.2f} МБ)")
        if file_size < 10000:
            print(f"*** ВНИМАНИЕ: Файл очень маленький ({file_size} байт) - возможно, результат пустой ***")
        
        # Очищаем временные файлы
        gdal.Unlink(vrt_path)
        os.unlink(cutline_path)
        
        return output_file.name
    
    def _get_resample_alg(self, method: str) -> int:
        """Получить константу GDAL для метода пересэмплинга"""
        method_map = {
            "nearest": gdal.GRA_NearestNeighbour,
            "bilinear": gdal.GRA_Bilinear,
            "cubic": gdal.GRA_Cubic,
            "cubicspline": gdal.GRA_CubicSpline,
            "lanczos": gdal.GRA_Lanczos,
            "average": gdal.GRA_Average,
            "mode": gdal.GRA_Mode,
            "max": gdal.GRA_Max,
            "min": gdal.GRA_Min,
            "med": gdal.GRA_Med,
            "q1": gdal.GRA_Q1,
            "q3": gdal.GRA_Q3,
        }
        return method_map.get(method, gdal.GRA_NearestNeighbour)
    
    def _save_metadata(
        self,
        output_path: Path,
        products: List[str],
        bbox: List[float],
        resample_to: Optional[Union[str, float]],
        resample_method: str
    ):
        """Сохранить _params.json и _metadata.txt"""
        
        # _params.json
        params_file = output_path / "_params.json"
        
        if not params_file.exists():
            # Первый вызов — сохраняем полные параметры
            metadata = {
                "query": self._scene._params.copy(),
                "processing": {
                    "operation": "merge_and_clip",
                    "resample_to": resample_to,
                    "resample_method": resample_method,
                    "bbox_used": bbox,
                    "products_used": products,
                    "timestamp": datetime.now().isoformat(),
                    "package_version": "1.0.0"
                }
            }
            with open(params_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # _metadata.txt
        metadata_file = output_path / "_metadata.txt"
        file_exists = metadata_file.exists()
        
        with open(metadata_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter='|')
            if not file_exists:
                writer.writerow(["dt", "satellite", "device", "station", "product", "file"])
            
            dt_str = self._scene.dt
            satellite = self._scene.satellite
            device = self._scene.device
            station = self._scene.station
            
            for product in products:
                filename = f"{dt_str.replace('-', '').replace(':', '').replace(' ', '_')[:15]}_{product}.tif"
                writer.writerow([dt_str, satellite, device, station, product, filename])