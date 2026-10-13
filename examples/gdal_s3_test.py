# gdal_s3_test.py
"""
Minimal test: can GDAL read/write /vsis3/ directly?

Reads .env (S3TOOL_BUCKET, S3TOOL_BASE, AWS_* variables) and configures
GDAL's /vsis3/ driver accordingly. Then writes a tiny GeoTIFF to S3 and
reads it back.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from osgeo import gdal, osr
from dotenv import load_dotenv


def setup_gdal_from_env():
    """Translate s3tool's .env into GDAL /vsis3/ config options."""
    load_dotenv(Path(__file__).parent.parent / ".env")

    bucket = os.getenv("S3TOOL_BUCKET")
    if not bucket:
        print("ERROR: S3TOOL_BUCKET is not set in .env")
        sys.exit(1)

    access = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    addressing = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not (access and secret):
        print("ERROR: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY missing in .env")
        sys.exit(1)

    # Debug: show what .env actually provided
    print("access repr:", repr(access))
    print("secret len:", len(secret),
          "first2:", repr(secret[:2]),
          "last2:", repr(secret[-2:]))
    print("region:", repr(region))
    print()

    # GDAL uses its own naming.
    # AWS_S3_ENDPOINT wants host[:port], no scheme.
    if endpoint:
        host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        gdal.SetConfigOption("AWS_S3_ENDPOINT", host)
        gdal.SetConfigOption("AWS_HTTPS", "YES" if endpoint.startswith("https") else "NO")

    gdal.SetConfigOption("AWS_ACCESS_KEY_ID", access)
    gdal.SetConfigOption("AWS_SECRET_ACCESS_KEY", secret)

    # Use AWS_DEFAULT_REGION (some clients read this instead of AWS_REGION).
    gdal.SetConfigOption("AWS_DEFAULT_REGION", region)
    gdal.SetConfigOption("AWS_REGION", region)

    # path-style vs virtual-hosted
    if addressing == "path":
        gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "FALSE")
    else:
        gdal.SetConfigOption("AWS_VIRTUAL_HOSTING", "TRUE")

    # /vsis3/ has no random write; GDAL will use a temp file behind the scenes.
    gdal.SetConfigOption("CPL_VSIL_USE_TEMP_FILE_FOR_RANDOM_WRITE", "YES")

    # diagnostics
    gdal.SetConfigOption("CPL_DEBUG", "ON")
    gdal.SetConfigOption("CPL_CURL_VERBOSE", "ON")

    return bucket, os.getenv("S3TOOL_BASE", "") or ""


def write_test_tif(vsi_path: str):
    """Write a tiny 4x4 float32 GeoTIFF to /vsis3/."""
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(vsi_path, 4, 4, 1, gdal.GDT_Float32,
                    options=["COMPRESS=LZW", "TILED=YES"])
    if ds is None:
        raise RuntimeError(f"cannot create {vsi_path}")

    ds.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, -1.0))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())

    arr = np.arange(16, dtype=np.float32).reshape(4, 4)
    ds.GetRasterBand(1).WriteArray(arr)
    ds = None
    return arr


def read_test_tif(vsi_path: str):
    """Read a GeoTIFF from /vsis3/ and return the array."""
    ds = gdal.Open(vsi_path)
    if ds is None:
        raise RuntimeError(f"cannot open {vsi_path} for reading")
    arr = ds.GetRasterBand(1).ReadAsArray()
    ds = None
    return arr


def main():
    gdal.UseExceptions()

    bucket, base = setup_gdal_from_env()
    prefix = (base.strip("/") + "/") if base else ""

    key = f"{prefix}gdal_s3_test.tif"
    vsi_path = f"/vsis3/{bucket}/{key}"

    print(f"bucket:   {bucket}")
    print(f"base:     {base!r}")
    print(f"vsi path: {vsi_path}")
    print()

    print("Writing test GeoTIFF to S3...")
    try:
        written = write_test_tif(vsi_path)
        print("  OK")
    except Exception as e:
        print(f"  FAILED: {e}")
        return

    print("Reading back from S3...")
    try:
        read = read_test_tif(vsi_path)
    except Exception as e:
        print(f"  FAILED: {e}")
        return

    if np.array_equal(written, read):
        print("  OK, arrays match")
    else:
        print("  MISMATCH")
        print("  written:", written)
        print("  read:   ", read)

    print()
    print(f"Object left in bucket: {key}")
    print("Remove it manually if you don't need it.")


if __name__ == "__main__":
    main()