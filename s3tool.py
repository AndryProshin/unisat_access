"""
s3tool.py -- convenient tool for working with S3 as a filesystem.

S3Tool provides a set of operations on "files" and "directories" in an
S3 bucket, with all relative paths resolved against the base directory
specified when the object is created.

Configuration:
  By default .env is read from the directory containing this file.
  Recognized variables:
    S3TOOL_BUCKET           -- bucket name (used when bucket is not passed)
    S3TOOL_BASE             -- base directory inside the bucket (default "")
    AWS_ENDPOINT_URL        -- custom endpoint (Ceph RGW, MinIO, etc.)
    AWS_ACCESS_KEY_ID       -- access key
    AWS_SECRET_ACCESS_KEY   -- secret key
    AWS_S3_ADDRESSING_STYLE -- "path" or "virtual"
  If an explicit s3_client is passed to the constructor, .env is not used
  for building the client (but bucket/base defaults still apply).

Public API style -- no exceptions:
  - "does" operations    -> bool (False = error, details in get_error_*)
  - "returns" operations -> data | None (None = error)
  - "checks" operations  -> bool in the direct sense

All paths accepted and returned by methods are relative to base.

Naming scheme: "<side>_file" / "<side>_dir" is the source object,
"<other>_base_dir" is the parent directory it is placed into. The
object name is always taken from the source (basename), never changed.
Uploading a local folder "foo" into s3_base_dir="bar" yields
base/bar/foo/...; downloading base/bar/foo/... into local_base_dir="."
yields ./foo/...

Mask works like in shell: applied to the name (last component of the
path), case-sensitive, recursion is a separate flag.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
)
from dotenv import load_dotenv


# Load .env from the directory containing this file (if it exists).
# Explicit s3_client in the constructor bypasses this configuration.
load_dotenv(Path(__file__).resolve().parent / ".env")


READY_EXT = ".rdy"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class S3ToolError(Exception):
    """Fatal error when creating S3Tool or explicitly requested."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ---------------------------------------------------------------------------
# boto3 error mapping
# ---------------------------------------------------------------------------

def _map_client_error(exc: ClientError) -> tuple[str, str]:
    err = exc.response.get("Error", {}) or {}
    code = err.get("Code", "UNKNOWN")

    if code in ("NoSuchBucket", "NoSuchKey", "404", "NotFound"):
        return "NOT_FOUND", f"not found: {err.get('Message', code)}"
    if code in ("AccessDenied", "403", "InvalidAccessKeyId", "SignatureDoesNotMatch"):
        return "ACCESS_DENIED", f"access denied: {err.get('Message', code)}"
    if code in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
        return "ALREADY_EXISTS", f"already exists: {err.get('Message', code)}"

    return "UNKNOWN", f"{code}: {err.get('Message', '')}"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class S3Tool:
    """Work with S3 as a filesystem."""

    ERR_NOT_FOUND = "NOT_FOUND"
    ERR_ALREADY_EXISTS = "ALREADY_EXISTS"
    ERR_ACCESS_DENIED = "ACCESS_DENIED"
    ERR_NETWORK = "NETWORK"
    ERR_INVALID_PATH = "INVALID_PATH"
    ERR_UNKNOWN = "UNKNOWN"

    def __init__(
        self,
        bucket: Optional[str] = None,
        base: Optional[str] = None,
        raise_on_fatal: bool = False,
        s3_client=None,
    ) -> None:
        """
        :param bucket:          bucket name. If None, taken from
                                S3TOOL_BUCKET in .env.
        :param base:            base "directory" for all relative paths.
                                If None, taken from S3TOOL_BASE in .env
                                (default ""). Empty string -- bucket root.
        :param raise_on_fatal:  what to do on fatal error:
                                False (default) -- stderr + sys.exit(1);
                                True            -- raise S3ToolError.
        :param s3_client:       optional preconfigured boto3 client. If
                                given, .env is not used to build the client.
        """
        if bucket is None:
            bucket = os.getenv("S3TOOL_BUCKET")
        if base is None:
            base = os.getenv("S3TOOL_BASE", "") or ""

        if not bucket:
            self._fatal(
                "INVALID_PATH",
                "bucket is not set (pass it explicitly or set S3TOOL_BUCKET in .env)",
                raise_on_fatal,
            )
            return

        self.bucket = bucket
        self.base = self._normalize(base)
        self._error_code: Optional[str] = None
        self._error_message: Optional[str] = None
        self._warning: Optional[str] = None

        if s3_client is not None:
            self.client = s3_client
        else:
            try:
                self.client = self._build_client_from_env()
            except (NoCredentialsError, NoRegionError, BotoCoreError) as e:
                self._fatal("ACCESS_DENIED", f"cannot create S3 client: {e}", raise_on_fatal)
                return

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._fatal(code, f"cannot access bucket {self.bucket!r}: {msg}", raise_on_fatal)
        except (EndpointConnectionError, BotoCoreError) as e:
            self._fatal("NETWORK", f"cannot reach S3: {e}", raise_on_fatal)

    @staticmethod
    def _build_client_from_env():
        """Build a boto3 S3 client from AWS_* variables (loaded from .env)."""
        endpoint = os.getenv("AWS_ENDPOINT_URL")
        addressing = os.getenv("AWS_S3_ADDRESSING_STYLE")

        kwargs = {}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        if addressing:
            kwargs["config"] = Config(s3={"addressing_style": addressing})

        return boto3.client("s3", **kwargs)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_error_code(self) -> Optional[str]:
        return self._error_code

    def get_error_message(self) -> Optional[str]:
        return self._error_message

    def get_warning(self) -> Optional[str]:
        return self._warning

    def _clear_state(self) -> None:
        self._error_code = None
        self._error_message = None
        self._warning = None

    def _set_error(self, code: str, message: str) -> None:
        self._error_code = code
        self._error_message = message

    def _set_warning(self, message: str) -> None:
        self._warning = message

    def _fatal(self, code: str, message: str, raise_on_fatal: bool) -> None:
        if raise_on_fatal:
            raise S3ToolError(code, message)
        print(f"S3Tool: [{code}] {message}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Path utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(prefix: Optional[str]) -> str:
        """'' -> ''; otherwise with a trailing '/'."""
        if not prefix:
            return ""
        return prefix if prefix.endswith("/") else prefix + "/"

    @staticmethod
    def _join_prefix(prefix: str, name: str) -> str:
        """Join a prefix and a name into a clean relative path.

        Guarantees exactly one '/' between non-empty parts, no leading
        or trailing '/'. Empty prefix + name -> name.
        """
        prefix = (prefix or "").strip("/")
        name = (name or "").strip("/")
        if prefix and name:
            return f"{prefix}/{name}"
        return prefix or name

    def _abs(self, rel: str) -> str:
        """Relative path -> S3 key (with base)."""
        rel = (rel or "").lstrip("/")
        return self.base + rel

    def _dir_key(self, rel: str) -> str:
        """Directory prefix key (with trailing '/')."""
        key = self._abs(rel)
        if key and not key.endswith("/"):
            key += "/"
        return key

    def _rel(self, key: str) -> str:
        """S3 key -> path relative to base."""
        if self.base and key.startswith(self.base):
            return key[len(self.base):]
        return key

    # ------------------------------------------------------------------
    # Internal operations
    # ------------------------------------------------------------------

    def _list_objects(self, prefix: str, recursive: bool):
        """
        Return (files, dirs) -- flat lists of keys.
        With recursive=False, Delimiter='/' is used, and dirs are
        CommonPrefixes (direct subfolders).
        With recursive=True, no delimiter is set, so dirs is empty --
        folders are computed on the client side if needed (see list_dirs).
        On error (None, None) with the code set.
        """
        files: list[str] = []
        dirs: list[str] = []

        paginator = self.client.get_paginator("list_objects_v2")
        kwargs = {"Bucket": self.bucket, "Prefix": prefix}
        if not recursive:
            kwargs["Delimiter"] = "/"

        try:
            for page in paginator.paginate(**kwargs):
                for obj in page.get("Contents", []) or []:
                    key = obj["Key"]
                    if key == prefix:  # folder marker object
                        continue
                    files.append(key)
                for cp in page.get("CommonPrefixes", []) or []:
                    dirs.append(cp["Prefix"])
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return None, None
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return None, None

        return files, dirs

    def _existing_keys_under(self, prefix: str) -> Optional[set]:
        """
        All keys under prefix (recursive), in a single paginated pass.
        Used for pre-checking conflicts in upload_dir.
        On error -- None.
        """
        result: set = set()
        paginator = self.client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []) or []:
                    result.add(obj["Key"])
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return None
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return None
        return result

    @staticmethod
    def _match_mask(name: str, mask: Optional[str]) -> bool:
        """
        Shell-like mask: applied to the name, case-sensitive.
        fnmatchcase (not fnmatch) -- so that on Windows case is not
        lowercased. Names never contain a slash, so a slash in the mask
        simply matches nothing.
        """
        if not mask:
            return True
        return fnmatch.fnmatchcase(name, mask)

    @staticmethod
    def _name_of(key: str) -> str:
        k = key.rstrip("/")
        return k.rsplit("/", 1)[-1] if "/" in k else k

    def _object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            code, _ = _map_client_error(e)
            if code == "NOT_FOUND":
                return False
            raise

    # ------------------------------------------------------------------
    # Files: listing
    # ------------------------------------------------------------------

    def list_files(
        self,
        path: str = "",
        mask: Optional[str] = None,
        recursive: bool = False,
    ) -> Optional[list[str]]:
        """
        List files in base/path.
        Returns paths relative to base.
        mask -- by file name (last component), shell-like.
        On error -- None.
        """
        self._clear_state()
        prefix = self._dir_key(path)
        files, _ = self._list_objects(prefix, recursive)
        if files is None:
            return None

        result = []
        for key in files:
            if self._match_mask(self._name_of(key), mask):
                result.append(self._rel(key))
        return result

    def file_exists(self, path: str) -> bool:
        """Whether a file exists exactly at base/path."""
        self._clear_state()
        key = self._abs(path)
        try:
            return self._object_exists(key)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False

    # ------------------------------------------------------------------
    # Files: S3 <-> local disk
    # ------------------------------------------------------------------

    def download_file(self, s3_file: str, local_base_dir: str) -> bool:
        """
        Download base/s3_file to local_base_dir/<basename(s3_file)>.
        The source file name is preserved on the local side.
        If the local file already exists -- ALREADY_EXISTS.
        """
        self._clear_state()

        name = self._name_of(s3_file)
        if not name:
            self._set_error("INVALID_PATH", "s3_file is empty")
            return False

        local_file = os.path.join(local_base_dir, name)
        if os.path.exists(local_file):
            self._set_error("ALREADY_EXISTS", f"local file already exists: {local_file}")
            return False

        key = self._abs(s3_file)
        try:
            self.client.download_file(self.bucket, key, local_file)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False
        return True

    def upload_file(self, local_file: str, s3_base_dir: str) -> bool:
        """
        Upload local file local_file to base/s3_base_dir/<basename(local_file)>.
        The source file name is preserved in S3.
        If the s3 object already exists -- ALREADY_EXISTS.
        """
        self._clear_state()
        if not os.path.isfile(local_file):
            self._set_error("NOT_FOUND", f"local file not found: {local_file}")
            return False

        name = os.path.basename(local_file)
        rel = self._join_prefix(s3_base_dir, name)
        key = self._abs(rel)
        try:
            if self._object_exists(key):
                self._set_error("ALREADY_EXISTS", f"s3 object already exists: {key}")
                return False
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False

        try:
            self.client.upload_file(local_file, self.bucket, key)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False
        return True

    # ------------------------------------------------------------------
    # Files: S3 <-> memory
    # ------------------------------------------------------------------

    def download_file_to_memory(self, s3_file: str) -> Optional[bytes]:
        """Read base/s3_file into memory. On error -- None."""
        self._clear_state()
        key = self._abs(s3_file)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return None
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return None

    def upload_file_from_memory(self, s3_file: str, data: bytes) -> bool:
        """
        Write bytes to base/s3_file.
        If the object already exists -- ALREADY_EXISTS.
        """
        self._clear_state()
        key = self._abs(s3_file)
        try:
            if self._object_exists(key):
                self._set_error("ALREADY_EXISTS", f"s3 object already exists: {key}")
                return False
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False

        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False
        return True

    # ------------------------------------------------------------------
    # Files: removal
    # ------------------------------------------------------------------

    def remove_file(self, s3_file: str) -> bool:
        self._clear_state()
        key = self._abs(s3_file)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False
        return True

    # ------------------------------------------------------------------
    # Directories: listing
    # ------------------------------------------------------------------

    def list_dirs(
        self,
        path: str = "",
        mask: Optional[str] = None,
        recursive: bool = False,
    ) -> Optional[list[str]]:
        """
        List directories inside base/path.
        Returns paths relative to base, WITHOUT trailing '/'.
        mask -- by folder name (last component), shell-like.
        On error -- None.
        """
        self._clear_state()
        prefix = self._dir_key(path)

        if recursive:
            files, _ = self._list_objects(prefix, recursive=True)
            if files is None:
                return None
            dirs_set: set[str] = set()
            for key in files:
                tail = key[len(prefix):]
                parts = tail.split("/")
                for i in range(1, len(parts)):
                    sub = "/".join(parts[:i])
                    if sub:
                        dirs_set.add(prefix + sub + "/")
            raw_dirs = sorted(dirs_set)
        else:
            _, dirs = self._list_objects(prefix, recursive=False)
            if dirs is None:
                return None
            raw_dirs = dirs

        result = []
        for d in raw_dirs:
            if self._match_mask(self._name_of(d), mask):
                result.append(self._rel(d.rstrip("/")))
        return result

    def dir_exists(self, path: str) -> bool:
        """True if there is at least one object with prefix base/path/."""
        self._clear_state()
        prefix = self._dir_key(path)
        files, dirs = self._list_objects(prefix, recursive=False)
        if files is None:
            return False
        return bool(files or dirs)

    # ------------------------------------------------------------------
    # Directories: S3 <-> local disk
    # ------------------------------------------------------------------

    def download_dir(self, s3_dir: str, local_base_dir: str,
                     overwrite: bool = False,
                     make_rdy: bool = False) -> bool:
        """
        Download base/s3_dir to local_base_dir/<basename(s3_dir)>/.

        The source directory name is preserved on the local side:
        download_dir("scenes/ndvi_125", ".") creates ./ndvi_125/.

        Empty s3_dir -- INVALID_PATH.
        If overwrite=False and the target folder or at least one target
        file already exists -- ALREADY_EXISTS (checked before starting).
        If overwrite=True -- existing local files are overwritten,
        extra ones (not in S3) are not touched.

        If make_rdy=True, a marker file <basename(s3_dir)>.rdy is
        created in local_base_dir after a successful download. No marker
        is created if the download fails.
        """
        self._clear_state()
        s3_dir = (s3_dir or "").strip("/")
        if not s3_dir:
            self._set_error("INVALID_PATH", "s3_dir is empty")
            return False

        name = s3_dir.rsplit("/", 1)[-1]
        target_dir = os.path.join(local_base_dir, name)
        prefix = self._dir_key(s3_dir)

        files, _ = self._list_objects(prefix, recursive=True)
        if files is None:
            return False

        planned = []
        for key in files:
            rel = key[len(prefix):] if key.startswith(prefix) else key
            local_path = os.path.join(target_dir, rel.replace("/", os.sep))
            if not overwrite and os.path.exists(local_path):
                self._set_error("ALREADY_EXISTS", f"local file already exists: {local_path}")
                return False
            planned.append((key, local_path))

        if not overwrite and os.path.exists(target_dir):
            self._set_error("ALREADY_EXISTS", f"local directory already exists: {target_dir}")
            return False

        for key, local_path in planned:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            try:
                self.client.download_file(self.bucket, key, local_path)
            except ClientError as e:
                code, msg = _map_client_error(e)
                self._set_error(code, f"failed on {key}: {msg}")
                return False
            except (EndpointConnectionError, BotoCoreError) as e:
                self._set_error("NETWORK", f"failed on {key}: {e}")
                return False

        if make_rdy:
            marker_path = os.path.join(local_base_dir, name + READY_EXT)
            try:
                with open(marker_path, "w"):
                    pass
            except OSError as e:
                self._set_error("UNKNOWN", f"cannot create marker {marker_path}: {e}")
                return False

        return True

    def upload_dir(self, local_dir: str, s3_base_dir: str = "",
                   make_rdy: bool = False) -> bool:
        """
        Upload local folder local_dir to
        base/s3_base_dir/<basename(local_dir)>/.

        The source directory name is preserved in S3:
        upload_dir("ndvi_125", s3_base_dir="scenes") yields
        base/scenes/ndvi_125/....

        Empty s3_base_dir -- uploads directly into base
        (base/<basename(local_dir)>/...).
        Conflicts are checked with a SINGLE list_objects_v2 call.

        If make_rdy=True, a marker object
        s3_base_dir/<basename(local_dir)>.rdy is created after a
        successful upload. No marker is created if the upload fails.
        """
        self._clear_state()
        if not os.path.isdir(local_dir):
            self._set_error("NOT_FOUND", f"local directory not found: {local_dir}")
            return False

        name = os.path.basename(os.path.normpath(local_dir))
        dst_prefix = self._dir_key(self._join_prefix(s3_base_dir, name))

        planned = []
        for root, _dirs, filenames in os.walk(local_dir):
            for fname in filenames:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, local_dir).replace(os.sep, "/")
                planned.append((full, dst_prefix + rel))

        existing = self._existing_keys_under(dst_prefix)
        if existing is None:
            return False

        conflicts = [key for _full, key in planned if key in existing]
        if conflicts:
            self._set_error(
                "ALREADY_EXISTS",
                "s3 objects already exist: " + ", ".join(conflicts),
            )
            return False

        for full, key in planned:
            try:
                self.client.upload_file(full, self.bucket, key)
            except ClientError as e:
                code, msg = _map_client_error(e)
                self._set_error(code, f"failed on {key}: {msg}")
                return False
            except (EndpointConnectionError, BotoCoreError) as e:
                self._set_error("NETWORK", f"failed on {key}: {e}")
                return False

        if make_rdy:
            marker_key = self._abs(self._join_prefix(s3_base_dir, name + READY_EXT))
            try:
                self.client.put_object(Bucket=self.bucket, Key=marker_key, Body=b"")
            except ClientError as e:
                code, msg = _map_client_error(e)
                self._set_error(code, f"failed to create marker {marker_key}: {msg}")
                return False
            except (EndpointConnectionError, BotoCoreError) as e:
                self._set_error("NETWORK", f"failed to create marker {marker_key}: {e}")
                return False

        return True

    # ------------------------------------------------------------------
    # Directories: removal
    # ------------------------------------------------------------------

    def remove_dir(self, path: str = "") -> bool:
        """
        Recursively remove base/path with all contents.
        If no objects -- success (no-op).
        """
        self._clear_state()
        prefix = self._dir_key(path)

        files, dirs = self._list_objects(prefix, recursive=True)
        if files is None:
            return False

        all_keys = list(files)
        for d in dirs:
            if d not in all_keys:
                all_keys.append(d)

        if not all_keys:
            return True

        try:
            for i in range(0, len(all_keys), 1000):
                chunk = all_keys[i:i + 1000]
                self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
                )
        except ClientError as e:
            code, msg = _map_client_error(e)
            self._set_error(code, msg)
            return False
        except (EndpointConnectionError, BotoCoreError) as e:
            self._set_error("NETWORK", str(e))
            return False
        return True

    # ------------------------------------------------------------------
    # Ready directories (.rdy)
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_orphans(orphans: list[str]) -> Optional[str]:
        """Build a single summary warning for orphan markers."""
        if not orphans:
            return None
        names = ", ".join(o + READY_EXT for o in orphans)
        return f"{len(orphans)} orphan marker(s) found: {names}"

    def find_ready_pairs_local(self, local_root: str) -> Optional[list[str]]:
        """
        Find names of ready pairs in a local directory.
        A pair is <name>/ + <name>.rdy in the same root.
        Returns a sorted list of names, or None on error.
        Orphan markers produce a summary warning (get_warning()).
        """
        self._clear_state()

        pairs, warning = self._scan_local_pairs(local_root)
        if pairs is None:
            return None
        if warning:
            self._set_warning(warning)
        return pairs

    def find_ready_pairs_s3(self, prefix: str = "") -> Optional[list[str]]:
        """
        Find names of ready pairs under base/prefix in S3.
        A pair is <name>/ + <name>.rdy at the same level.
        Returns a sorted list of names, or None on error.
        Orphan markers produce a summary warning (get_warning()).
        """
        self._clear_state()

        pairs, warning = self._scan_s3_pairs(prefix)
        if pairs is None:
            return None
        if warning:
            self._set_warning(warning)
        return pairs

    def upload_one_ready_pair(
        self,
        local_root: str,
        name: str,
        dst_prefix: str = "",
        keep: bool = False,
    ) -> bool:
        """
        Upload a single ready pair <name>/ + <name>.rdy from local_root
        to base/dst_prefix/<name>/ + base/dst_prefix/<name>.rdy.

        If keep=False (default), local copies are removed after upload.
        If keep=True, local copies are kept.

        Returns True on success, False on error.
        Does not clear state (used inside upload_ready_dirs).
        Preserves any previously set warning across nested calls.
        """
        saved_warning = self._warning

        local_dir = os.path.join(local_root, name)
        local_marker = os.path.join(local_root, name + READY_EXT)

        if not os.path.isdir(local_dir):
            self._set_error("NOT_FOUND", f"local directory not found: {local_dir}")
            self._warning = saved_warning
            return False
        if not os.path.isfile(local_marker):
            self._set_error("NOT_FOUND", f"local marker not found: {local_marker}")
            self._warning = saved_warning
            return False

        dst_marker = self._join_prefix(dst_prefix, name + READY_EXT)

        # upload_dir preserves the source directory name, so passing
        # dst_prefix (the parent) is enough: the resulting key will be
        # base/dst_prefix/<name>/...
        if not self.upload_dir(local_dir, dst_prefix):
            self._warning = saved_warning
            return False
        if not self.upload_file(local_marker, dst_prefix):
            self._warning = saved_warning
            return False

        if not keep:
            shutil.rmtree(local_dir)
            os.remove(local_marker)

        self._warning = saved_warning
        return True

    def download_one_ready_pair(
        self,
        name: str,
        src_prefix: str = "",
        local_root: str = ".",
        keep: bool = False,
    ) -> bool:
        """
        Download a single ready pair <name>/ + <name>.rdy from
        base/src_prefix to local_root, create local marker.

        If keep=False (default), S3 copies are removed after download.
        If keep=True, S3 copies are kept.

        Returns True on success, False on error.
        Does not clear state (used inside download_ready_dirs).
        Preserves any previously set warning across nested calls.
        """
        saved_warning = self._warning

        src_dir = self._join_prefix(src_prefix, name)
        src_marker = src_dir + READY_EXT

        if not self.download_dir(src_dir, local_root, overwrite=True):
            self._warning = saved_warning
            return False

        local_marker = os.path.join(local_root, name + READY_EXT)
        try:
            with open(local_marker, "w"):
                pass
        except OSError as e:
            self._set_error("UNKNOWN", f"cannot create local marker {local_marker}: {e}")
            self._warning = saved_warning
            return False

        if not keep:
            if not self.remove_dir(src_dir):
                self._warning = saved_warning
                return False
            if not self.remove_file(src_marker):
                self._warning = saved_warning
                return False

        self._warning = saved_warning
        return True

    def upload_ready_dirs(
        self,
        local_root: str,
        dst_prefix: str = "",
        keep: bool = False,
        retries: int = 2,
        retry_delay: float = 2,
    ) -> bool:
        """
        Move ready pairs from local_root to base/dst_prefix.

        A pair is <name>/ + <name>.rdy in local_root.
        For each pair:
          1. Upload directory to S3.
          2. Upload marker to S3.
          3. Remove local directory (skipped if keep=True).
          4. Remove local marker (skipped if keep=True).
        Retried as a whole up to `retries` times, only on NETWORK.

        Orphan markers produce a summary warning (get_warning()).
        """
        self._clear_state()

        pairs, warning = self._scan_local_pairs(local_root)
        if pairs is None:
            return False
        if warning:
            self._set_warning(warning)
        if not pairs:
            return True

        for name in pairs:
            for attempt in range(1, retries + 1):
                if not self.upload_one_ready_pair(local_root, name, dst_prefix, keep=keep):
                    if self._error_code == "NETWORK" and attempt < retries:
                        time.sleep(retry_delay)
                        continue
                    return False
                break

        return True

    def download_ready_dirs(
        self,
        src_prefix: str = "",
        local_root: str = ".",
        keep: bool = False,
        retries: int = 2,
        retry_delay: float = 2,
    ) -> bool:
        """
        Move ready pairs from base/src_prefix to local_root.

        A pair is <name>/ + <name>.rdy in S3.
        For each pair:
          1. Download directory locally.
          2. Create local marker.
          3. Remove S3 directory (skipped if keep=True).
          4. Remove S3 marker (skipped if keep=True).
        Retried as a whole up to `retries` times, only on NETWORK.

        Orphan markers produce a summary warning (get_warning()).
        """
        self._clear_state()

        pairs, warning = self._scan_s3_pairs(src_prefix)
        if pairs is None:
            return False
        if warning:
            self._set_warning(warning)
        if not pairs:
            return True

        for name in pairs:
            for attempt in range(1, retries + 1):
                if not self.download_one_ready_pair(name, src_prefix, local_root, keep=keep):
                    if self._error_code == "NETWORK" and attempt < retries:
                        time.sleep(retry_delay)
                        continue
                    return False
                break

        return True

    # ------------------------------------------------------------------
    # Internal: pair scanning (no state clearing)
    # ------------------------------------------------------------------

    def _scan_local_pairs(self, local_root: str) -> tuple[Optional[list[str]], Optional[str]]:
        """
        Scan local_root for ready pairs.
        Returns (pairs, warning). On error -- (None, None) with error set.
        Does not touch warning state.
        """
        if not os.path.isdir(local_root):
            self._set_error("NOT_FOUND", f"local directory not found: {local_root}")
            return None, None

        entries = os.listdir(local_root)
        dirs = {e for e in entries if os.path.isdir(os.path.join(local_root, e))}
        markers = {e[:-len(READY_EXT)] for e in entries if e.endswith(READY_EXT)}

        pairs = sorted(dirs & markers)
        warning = self._summarize_orphans(sorted(markers - dirs))
        return pairs, warning

    def _scan_s3_pairs(self, prefix: str) -> tuple[Optional[list[str]], Optional[str]]:
        """
        Scan base/prefix for ready pairs.
        Returns (pairs, warning). On error -- (None, None) with error set.
        Does not touch warning state.
        """
        p = self._dir_key(prefix)

        files, _ = self._list_objects(p, recursive=False)
        if files is None:
            return None, None

        names_rel = [self._name_of(f) for f in files]
        markers = {n[:-len(READY_EXT)] for n in names_rel if n.endswith(READY_EXT)}

        _, dirs = self._list_objects(p, recursive=False)
        if dirs is None:
            return None, None
        dir_names = {d.rstrip("/").rsplit("/", 1)[-1] for d in dirs}

        pairs = sorted(markers & dir_names)
        warning = self._summarize_orphans(sorted(markers - dir_names))
        return pairs, warning