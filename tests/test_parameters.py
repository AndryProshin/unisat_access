# tests/test_parameters.py

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unisat_api.parameters import Parameters
from unisat_api import config

import unittest
import json
from unittest.mock import patch, Mock


class TestParameters(unittest.TestCase):
    
    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.original_presets_dir = config.PRESETS_DIR
        self.original_metadata_url = config.METADATA_BASE_URL
        self.original_collections_dir = config.COLLECTIONS_DIR
        self.original_users_dir = config.USERS_DIR
        
        self.temp_dir = Path("./test_temp")
        self.temp_dir.mkdir(exist_ok=True)
        config.PRESETS_DIR = self.temp_dir / "presets"
        config.PRESETS_DIR.mkdir(exist_ok=True)
        
        # Создаём поддиректории
        config.COLLECTIONS_DIR = config.PRESETS_DIR / "collections"
        config.USERS_DIR = config.PRESETS_DIR / "users"
        config.COLLECTIONS_DIR.mkdir(exist_ok=True)
        config.USERS_DIR.mkdir(exist_ok=True)
        
        self.mock_schema = {
            "required": ["dt", "dt_from", "bbox"],
            "valid": {
                "dt": "DATE_OR_DATETIME",
                "dt_from": "DATE_OR_DATETIME",
                "bbox": "BBOX",
                "limit": "NUMBER",
                "max_cloudiness": "NUMBER",
                "satellites": "LIST",
                "products": "LIST",
                "devices": "LIST",
                "stations": "LIST"
            },
            "desc": {
                "dt": "Start of time interval",
                "dt_from": "End of time interval",
                "bbox": "BBOX (minx, miny, maxx, maxy)"
            }
        }
    
    def tearDown(self):
        config.PRESETS_DIR = self.original_presets_dir
        config.METADATA_BASE_URL = self.original_metadata_url
        config.COLLECTIONS_DIR = self.original_collections_dir
        config.USERS_DIR = self.original_users_dir
        
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_preset(self, name, data, is_collection=True):
        """Создаёт тестовый пресет в соответствующей директории"""
        if is_collection:
            preset_dir = config.COLLECTIONS_DIR
        else:
            preset_dir = config.USERS_DIR
        
        preset_dir.mkdir(parents=True, exist_ok=True)
        preset_file = preset_dir / f"{name}.json"
        with open(preset_file, 'w') as f:
            json.dump(data, f)
    
    def _create_params_with_minimal(self):
        """Создаёт параметры с минимальными обязательными полями"""
        return {
            "dt_from": "2024-01-01 00:00:00",
            "dt": "2024-01-02 00:00:00",
            "bbox": [41, 41, 45, 45]
        }
    
    @patch('unisat_api.parameters.requests')
    def test_load_schema_success(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        
        self.assertIsNotNone(params.get_schema())
        self.assertIn("required", params.get_schema())
    
    @patch('unisat_api.parameters.requests')
    def test_load_schema_failure(self, mock_requests):
        mock_requests.get.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            Parameters(params=self._create_params_with_minimal())
    
    @patch('unisat_api.parameters.requests')
    def test_load_collection_success(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        preset_data = {
            "satellites": ["SENTINEL-2A", "SENTINEL-2B"],
            "products": ["channel4_l2a", "channel8_l2a"],
            "max_cloudiness": 80,
            "bbox": [41, 41, 45, 45],
            "dt_from": None,
            "dt": None
        }
        self._create_preset("sentinel2_boa", preset_data, is_collection=True)
        
        params = Parameters(
            collection="sentinel2_boa",
            params={
                "dt_from": "2024-01-01 00:00:00",
                "dt": "2024-01-02 00:00:00"
            }
        )
        
        self.assertEqual(params["satellites"], ["SENTINEL-2A", "SENTINEL-2B"])
        self.assertEqual(params["max_cloudiness"], 80)
    
    @patch('unisat_api.parameters.requests')
    def test_load_user_preset_success(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        preset_data = {
            "satellites": ["SENTINEL-2A", "SENTINEL-2B"],
            "products": ["channel4_l2a", "channel8_l2a"],
            "max_cloudiness": 80,
            "bbox": [41, 41, 45, 45],
            "dt_from": None,
            "dt": None
        }
        self._create_preset("my_preset", preset_data, is_collection=False)
        
        params = Parameters(
            user_preset="my_preset",
            params={
                "dt_from": "2024-01-01 00:00:00",
                "dt": "2024-01-02 00:00:00"
            }
        )
        
        self.assertEqual(params["satellites"], ["SENTINEL-2A", "SENTINEL-2B"])
        self.assertEqual(params["max_cloudiness"], 80)
    
    @patch('unisat_api.parameters.requests')
    def test_collection_not_found(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        with self.assertRaises(FileNotFoundError):
            Parameters(collection="nonexistent", params=self._create_params_with_minimal())
    
    @patch('unisat_api.parameters.requests')
    def test_user_preset_not_found(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        with self.assertRaises(FileNotFoundError):
            Parameters(user_preset="nonexistent", params=self._create_params_with_minimal())
    
    @patch('unisat_api.parameters.requests')
    def test_override_preset_with_params(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        preset_data = {
            "satellites": ["SENTINEL-2A", "SENTINEL-2B"],
            "max_cloudiness": 80,
            "bbox": [41, 41, 45, 45]
        }
        self._create_preset("test_preset", preset_data, is_collection=True)
        
        params = Parameters(
            collection="test_preset",
            params={
                "max_cloudiness": 50,
                "dt_from": "2024-01-01 00:00:00",
                "dt": "2024-01-02 00:00:00"
            }
        )
        
        self.assertEqual(params["max_cloudiness"], 50)
        self.assertEqual(params["dt_from"], "2024-01-01 00:00:00")
        self.assertEqual(params["satellites"], ["SENTINEL-2A", "SENTINEL-2B"])
    
    @patch('unisat_api.parameters.requests')
    def test_validation_missing_required(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        with self.assertRaises(SystemExit):
            Parameters(params={"limit": 100})
    
    @patch('unisat_api.parameters.requests')
    def test_validation_correct_params(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        
        self.assertEqual(params["dt_from"], "2024-01-01 00:00:00")
        self.assertEqual(params["dt"], "2024-01-02 00:00:00")
        self.assertEqual(params["bbox"], [41, 41, 45, 45])
    
    @patch('unisat_api.parameters.requests')
    def test_save_user_preset(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        params.set("max_cloudiness", 50)
        params.save("new_preset")
        
        preset_file = config.USERS_DIR / "new_preset.json"
        self.assertTrue(preset_file.exists())
        
        with open(preset_file) as f:
            saved = json.load(f)
        
        self.assertEqual(saved["max_cloudiness"], 50)
    
    @patch('unisat_api.parameters.requests')
    def test_get_required_params(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        required = params.get_required_params()
        
        self.assertIn("dt", required)
        self.assertIn("dt_from", required)
        self.assertIn("bbox", required)
    
    @patch('unisat_api.parameters.requests')
    def test_set_param_with_validation(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        params.set("max_cloudiness", 75)
        self.assertEqual(params["max_cloudiness"], 75)
        
        with self.assertRaises(SystemExit):
            params.set("bbox", "invalid")
    
    @patch('unisat_api.parameters.requests')
    def test_list_presets(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        self._create_preset("collection1", {"bbox": [1, 2, 3, 4]}, is_collection=True)
        self._create_preset("collection2", {"bbox": [5, 6, 7, 8]}, is_collection=True)
        self._create_preset("user1", {"bbox": [9, 10, 11, 12]}, is_collection=False)
        
        presets = Parameters.list_presets()
        
        self.assertIn("collection1", presets)
        self.assertIn("collection2", presets)
        self.assertIn("user1", presets)
    
    @patch('unisat_api.parameters.requests')
    def test_get_parameters_description(self, mock_requests):
        mock_response = Mock()
        mock_response.json.return_value = self.mock_schema
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        params = Parameters(params=self._create_params_with_minimal())
        desc = params.get_parameters_description()
        
        self.assertIn("* bbox", desc)
        self.assertIn("* dt", desc)
        self.assertIn("limit", desc)


if __name__ == "__main__":
    unittest.main()