#!/usr/bin/env python3
"""Mirror static EDH artifacts to the approved Ningxia S3 prefix."""
import argparse
import hashlib
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve

import boto3
import yaml

EXCLUDED_PATHS = {
    "system/awscliv2",
    "system/python/pip_index_url",
    "system/python/pip_extra_index_url",
    "system/nodejs/npm_registry",
    "system/windows_dcv_monitoring/pip_index_url",
    "system/gpu/gpu_settings/nvidia/linux/tesla_drivers/public_driver_url_endpoint",
    "system/gpu/gpu_settings/amd/linux/radeon_repo_url",
}


def is_excluded(path):
    return any(
        path == excluded or path.startswith(f"{excluded}/") or path.endswith(f"/{excluded}")
        for excluded in EXCLUDED_PATHS
    )


def walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}/{key}" if path else key
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                if not is_excluded(child) and "%" not in value and not value.endswith(".git"):
                    yield value, node.get("sha256")
            else:
                yield from walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}/{index}")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str) -> dict:
    def merge(base: dict, override: dict) -> None:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merge(base[key], value)
            else:
                base[key] = value

    config: dict = {}
    for config_path in (item.strip() for item in path.split(",") if item.strip()):
        loaded = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{config_path} must contain a YAML mapping at its root")
        merge(config, loaded)
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="installer/default_config.yml")
    parser.add_argument("--region", default="cn-northwest-1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    base_uri = str(config.get("Config", {}).get("china_region", {}).get("artifact_base_uri", "")).rstrip("/")
    parsed = urlparse(base_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("Config.china_region.artifact_base_uri must be an s3:// URI")

    s3 = boto3.client("s3", region_name=args.region)
    prefix = parsed.path.strip("/")
    for url, expected_sha in walk(config["Parameters"]):
        key = "/".join(part for part in (prefix, url.split("://", 1)[1].lstrip("/")) if part)
        print(f"{url} -> s3://{parsed.netloc}/{key}")
        if args.dry_run:
            continue
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifact"
            urlretrieve(url, target)
            if expected_sha and sha256(target) != expected_sha:
                raise RuntimeError(f"SHA-256 mismatch: {url}")
            s3.upload_file(str(target), parsed.netloc, key)


if __name__ == "__main__":
    main()
