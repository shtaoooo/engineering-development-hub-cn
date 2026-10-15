# 宁夏区（cn-northwest-1）改造代码对照清单

> 基线：当前 Git `HEAD`。行号为修改后工作区行号。新增文件或新增代码块的“原始代码”标记为“无”。
>
> 本文覆盖宁夏适配涉及的全部工作区改动；`.kiro/` 不属于运行时代码，未纳入。
>
> 2026-10-15 补充：依据 `EDH 宁夏区源码与配置修改说明.md`，本文更新为部署时填写的宁夏制品桶占位符、RHEL 8.10 AMI 和资源镜像修复。

## 1. `installer/default_config.yml`

### [ ] 填写宁夏部署配置（修改后行 13-17）

原始代码：无 `china_region` 配置块。

修改后：
```yaml
# China-specific values belong in installer/config.cn-northwest-1.yml.
# Use both files with --config default_config.yml,config.cn-northwest-1.yml.
china_region:
  safe_defaults_enabled: true # disables unverified services
  artifact_base_uri: "" # Required in cn-northwest-1, e.g. s3://<bucket>/edh/artifacts
  ami_overrides: {} # {x86_64: {amazonlinux2023: ami-...}, arm64: {...}}
```

作用：定义宁夏安全默认开关、制品 S3 前缀和账户本地 AMI 覆盖入口。

### Lambda layer 私有 PyPI（修改后行 789-793）

原始代码：
```yaml
lambda_layers:
  Boto3Version: "1.43.68"
  CryptographyVersion: "48.0.0"
```

修改后：
```yaml
lambda_layers:
  Boto3Version: "1.43.68"
  CryptographyVersion: "48.0.0"
  pip_index_url: "https://mirrors.aliyun.com/pypi/simple/" # Public China PyPI mirror for Lambda layer builds
  pip_extra_index_url: "" # Optional secondary Python package index for Lambda layers
```

作用：让 CDK synth 构建 Lambda layer 时可使用企业或国内 PyPI 镜像。

### 节点 Python、npm 与 Windows wheelhouse 配置（修改后行 980-987、1154-1157、1231-1238）

原始代码：
```yaml
python:
  version: "3.13.13"
  url: "https://www.python.org/ftp/python/3.13.13/Python-3.13.13.tgz"
  sha256: "f9cde7b0e2ec8165d7326e2a0f59ea2686ce9d0c617dbbb3d66a7e54d31b74b9"

nodejs:
  url: "https://nodejs.org/dist/v24.15.0/node-v24.15.0-linux-x64.tar.xz"
  sha256: "472655581fb851559730c48763e0c9d3bc25975c59d518003fc0849d3e4ba0f6"

# Amazon DCV Settings
# https://aws.amazon.com/hpc/dcv/
dcv:
```

修改后：
```yaml
python:
  version: "3.13.13"
  url: "https://www.python.org/ftp/python/3.13.13/Python-3.13.13.tgz"
  sha256: "f9cde7b0e2ec8165d7326e2a0f59ea2686ce9d0c617dbbb3d66a7e54d31b74b9"
  # Optional private Python repository or offline wheelhouse. A wheelhouse
  # must contain every wheel required by the selected controller/node OS.
  pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
  pip_extra_index_url: ""
  pip_wheelhouse_s3_uri: ""

nodejs:
  url: "https://nodejs.org/dist/v24.15.0/node-v24.15.0-linux-x64.tar.xz"
  sha256: "472655581fb851559730c48763e0c9d3bc25975c59d518003fc0849d3e4ba0f6"
  npm_registry: "https://registry.npmmirror.com/" # Public China npm registry

# Amazon DCV Settings
# https://aws.amazon.com/hpc/dcv/
windows_dcv_monitoring:
  python_embed_url: "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
  get_pip_url: "https://bootstrap.pypa.io/get-pip.py"
  pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
  pip_wheelhouse_s3_uri: "" # Offline wheelhouse with boto3 and all transitive wheels
dcv:
```

作用：为 Linux 节点 Python、控制器 npm 和 Windows DCV monitoring 提供实际的阿里云 PyPI、npmmirror npm 源；wheelhouse 未预置时为空并回退到 PyPI。

## 2. `installer/config.cn-northwest-1.yml`（新增文件）

原始代码：文件不存在。

修改后（行 1-20）：
```yaml
# Ningxia deployment overlay for cn-northwest-1.
# Use with: --config installer/default_config.yml,installer/config.cn-northwest-1.yml
Config:
  china_region:
    safe_defaults_enabled: true
    # Replace <cn-artifact-bucket> before deployment with the approved Ningxia S3 bucket.
    artifact_base_uri: "s3://<cn-artifact-bucket>/edh/artifacts"
    ami_overrides:
      x86_64:
        rhel8: "ami-00ccfc1b12bbbabfc"
  lambda_layers:
    pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
    pip_extra_index_url: ""
  services:
    resources_mirroring:
      enabled: false
      method: "install-host"
Parameters:
  system:
    python:
      pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
      pip_extra_index_url: ""
      pip_wheelhouse_s3_uri: ""
    nodejs:
      npm_registry: "https://registry.npmmirror.com/"
    windows_dcv_monitoring:
      pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
      pip_wheelhouse_s3_uri: ""
```

作用：提供宁夏覆盖配置：部署前必须将 `<cn-artifact-bucket>` 替换为已预置制品的宁夏 S3 桶；RHEL 8.10 使用 `ami-00ccfc1b12bbbabfc`，并使用阿里云 PyPI 和 npmmirror。`resources_mirroring.enabled: false` 显式声明不创建云侧镜像执行器。

## 3. `installer/resources/src/helpers/installer/helpers.py`

### 支持“基础配置,覆盖配置”深度合并（修改后行 512-538）

原始代码：
```python
def get_install_properties(path: str) -> dict:
    # Retrieve SOCA configuration properties
    logger.debug(f"Configuration file path: {path}")
    try:
        with open(path, "r") as config_file:
            config_parameters = yaml.safe_load(config_file)
    except ScannerError as _err:
        logger.error(f"{path} is not a valid YAML file. Verify syntax, {_err}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error(
            f"{path} not found. Make sure the file exist and the path is correct."
        )
        sys.exit(1)

    if config_parameters:
        return config_parameters
    else:
        return {}
```

修改后：
```python
def get_install_properties(path: str) -> dict:
    """Load one or more comma-separated YAML configurations, merging later files."""
    def merge(base: dict, override: dict) -> dict:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merge(base[key], value)
            else:
                base[key] = value
        return base

    config_parameters: dict = {}
    for config_path in (item.strip() for item in path.split(",") if item.strip()):
        logger.debug(f"Configuration file path: {config_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                loaded = yaml.safe_load(config_file) or {}
        except ScannerError as _err:
            logger.error(f"{config_path} is not a valid YAML file. Verify syntax, {_err}")
            sys.exit(1)
        except FileNotFoundError:
            logger.error(f"{config_path} not found. Make sure the file exists and the path is correct.")
            sys.exit(1)
        if not isinstance(loaded, dict):
            logger.error(f"{config_path} must contain a YAML mapping at its root.")
            sys.exit(1)
        merge(config_parameters, loaded)

    return config_parameters
```

作用：后一个 YAML 覆盖前一个 YAML；使用 UTF-8 避免 Windows GBK 解码失败。

## 4. `installer/resources/src/helpers/installer/install_cli_args.py`

### 更新 `--config` 参数说明（修改后行 21-29）

原始代码：
```python
help=_("Path of custom config file(s). Defaults to default_config.yml ."),
```

修改后：
```python
help=_(
    "Path of a YAML config file, or comma-separated base and overlay files. Defaults to default_config.yml."
),
```

作用：在 CLI 帮助中说明覆盖配置用法。

## 5. `installer/edh_installer.sh`

### 安装器镜像源可配置化（修改后行 174-183）

原始代码：
```bash
PYENV_URL="https://pyenv.run"
INSTALLER_DIRECTORY=$(dirname $(realpath "$0"))
PYTHON_VENV="$INSTALLER_DIRECTORY/resources/src/envs/venv-py-installer"
NODEJS_BIN="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh"
export NVM_DIR="$INSTALLER_DIRECTORY/resources/src/envs/.nvm"
```

修改后：
```bash
# Corporate or China-local mirrors can be supplied without changing this file.
# pip and npm natively honor PIP_INDEX_URL, PIP_EXTRA_INDEX_URL and
# NPM_CONFIG_REGISTRY, which are inherited by the installer and CDK subprocesses.
PYENV_URL="${EDH_PYENV_URL:-https://pyenv.run}"
NODEJS_BIN="${EDH_NVM_INSTALL_URL:-https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh}"
INSTALLER_DIRECTORY=$(dirname $(realpath "$0"))
PYTHON_VENV="$INSTALLER_DIRECTORY/resources/src/envs/venv-py-installer"
export NVM_DIR="$INSTALLER_DIRECTORY/resources/src/envs/.nvm"

[[ -n "${PIP_INDEX_URL:-}" ]] && log_info "Using configured Python package index"
[[ -n "${NPM_CONFIG_REGISTRY:-}" ]] && log_info "Using configured npm registry"
```

作用：允许通过环境变量替换 pyenv/NVM 下载地址，并透传 pip/npm 私有源。

## 6. `installer/resources/src/cdk_construct.py`

### 宁夏 AMI 覆盖（修改后行 948-969）

原始代码：无。代码仅从发布版 `RegionMap` 获取 AMI。

修改后：
```python
# China AMIs are account and Region scoped. Allow a deployment config to
# supply tested local IDs without modifying release-managed 000-* maps.
if self._region == "cn-northwest-1":
    _cn_ami_overrides = get_config_key(
        key_name="Config.china_region.ami_overrides",
        required=False,
        expected_type=dict,
        default={},
    )
    for _arch, _base_os_map in _cn_ami_overrides.items():
        if _arch not in self.soca_resources["custom_ami_map"]:
            logger.warning(f"Ignoring unsupported China AMI architecture: {_arch}")
            continue
        if not isinstance(_base_os_map, dict):
            logger.warning(f"Ignoring invalid China AMI map for architecture: {_arch}")
            continue
        for _base_os, _ami_id in _base_os_map.items():
            if _ami_id:
                self.soca_resources["custom_ami_map"][_arch][_base_os] = _ami_id
```

作用：使用中国区账户内验证过的 AMI，不修改发布版区域映射。

### Lambda layer 私有 PyPI（修改后行 1366-1382）

原始代码：无。所有 layer 构建均只执行默认 `pip install`。

修改后：
```python
# Lambda layers are built during CDK synth. Private indexes keep that
# build path inside approved China/on-prem package mirrors.
_lambda_pip_args: list[str] = []
_lambda_pip_index_url = get_config_key(
    key_name="Config.lambda_layers.pip_index_url",
    required=False,
    default="",
)
_lambda_pip_extra_index_url = get_config_key(
    key_name="Config.lambda_layers.pip_extra_index_url",
    required=False,
    default="",
)
if _lambda_pip_index_url:
    _lambda_pip_args.extend(["--index-url", _lambda_pip_index_url])
if _lambda_pip_extra_index_url:
    _lambda_pip_args.extend(["--extra-index-url", _lambda_pip_extra_index_url])
```

原始代码（四个 pip 调用的共同尾部）：
```python
"--no-cache-dir",
"-q",
]
```

修改后（行 1416、1493、1564、1638，分别用于 boto3、redis、cryptography、psycopg layer）：
```python
"--no-cache-dir",
"-q",
*_lambda_pip_args,
]
```

作用：四种 Lambda layer 构建都能使用配置的 PyPI 镜像。

### AMI 缺失错误信息（修改后行 4564-4568）

原始代码：
```python
if _default_ami_for_instance is None:
    logger.fatal(
        "No AMI on region_map.yml found. Choose a different OS/Region or Architecture"
    )
```

修改后：
```python
if not _default_ami_for_instance:
    logger.fatal(
        f"No AMI configured for base OS {self._base_os}, architecture "
        f"{_instance_arch}, and region {region}. Add a matching RegionMap "
        "entry or Config.china_region.ami_overrides before deployment."
    )
```

作用：出现 AMI 缺失时指出宁夏 AMI 覆盖配置入口。

## 7. `installer/resources/src/install_soca.py`

### 宁夏安全默认值和静态制品重写（修改后行 195-291）

原始代码：无。安装流程没有中国区专用安全默认值或 S3 制品重写逻辑。

修改后：
```python
_CN_ARTIFACT_EXCLUDED_PATHS = {
    "system/awscliv2",
    "system/python/pip_index_url",
    "system/python/pip_extra_index_url",
    "system/nodejs/npm_registry",
    "system/gpu/gpu_settings/nvidia/linux/tesla_drivers/public_driver_url_endpoint",
    "system/gpu/gpu_settings/amd/linux/radeon_repo_url",
}


def rewrite_cn_artifact_urls(
    node: object, artifact_base_uri: str, path: str = ""
) -> None:
    """Rewrite static external artifacts to an approved Ningxia S3 prefix."""
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}/{key}" if path else key
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                if (
                    is_cn_artifact_excluded(child_path)
                    or "%" in value
                    or value.endswith(".git")
                ):
                    continue
                origin = value.split("://", 1)[1].lstrip("/")
                node[key] = f"{artifact_base_uri}/{origin}"
            else:
                rewrite_cn_artifact_urls(value, artifact_base_uri, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            rewrite_cn_artifact_urls(value, artifact_base_uri, f"{path}/{index}")


def apply_cn_northwest_defaults(install_properties: dict, region: str) -> None:
    if region != "cn-northwest-1":
        return

    config = install_properties.setdefault("Config", {})
    china_config = config.setdefault("china_region", {})
    artifact_base_uri = str(china_config.get("artifact_base_uri", "")).rstrip("/")
    if not artifact_base_uri.startswith("s3://"):
        logger.error(
            "Config.china_region.artifact_base_uri must be an approved s3:// URI "
            "when deploying to cn-northwest-1."
        )
        sys.exit(1)
    if not china_config.get("safe_defaults_enabled", True):
        logger.warning("China safe defaults disabled by configuration")
        return

    config.setdefault("network", {}).setdefault("aws_aga", {})["enabled"] = False
    config.setdefault("services", {}).setdefault("aws_batch", {})[
        "create_default_edh_environment"
    ] = False
    mirror_config = config.setdefault("services", {}).setdefault(
        "resources_mirroring", {}
    )
    mirror_config.update({"enabled": True, "method": "install-host", "failure_mode": "hard"})
    config.setdefault("services", {}).setdefault("usb_remotization", {})["enabled"] = False
    config.setdefault("analytics", {})["enabled"] = False
    config.setdefault("ai_assistant", {})["allowed_bedrock_model_ids"] = []
    config.setdefault("database", {})["provider"] = "sqlite"
    openpbs_config = (
        install_properties.setdefault("Parameters", {})
        .setdefault("system", {})
        .setdefault("scheduler", {})
        .setdefault("openpbs", {})
    )
    openpbs_config["deployment_type"] = "tgz"
    rewrite_cn_artifact_urls(install_properties.get("Parameters", {}), artifact_base_uri)
    dcv_config = config.setdefault("dcv", {})
    dcv_config["high_scale"] = False
    dcv_config.setdefault("pool", {})["enabled"] = False
    dcv_config.setdefault("session_sharing", {})["enabled"] = False
```

作用：仅在宁夏区启用最小功能集，要求配置本地制品 S3 前缀，并将可镜像静态下载地址改写到该前缀。

### 调用宁夏默认值（修改后行 746-749）

原始代码：无调用。

修改后：
```python
apply_cn_northwest_defaults(
    install_properties=_get_install_properties,
    region=install_parameters["region"],
)
```

作用：在区域确定后、后续资源校验前应用宁夏配置。

### OpenSearch 服务关联角色分区后缀（修改后行 804-809）

原始代码：
```python
_iam_iter = _iam_paginator.paginate(
    PathPrefix="/aws-service-role/opensearchservice.amazonaws.com"
)
```

修改后：
```python
_opensearch_service_principal = (
    "opensearchservice.amazonaws.com.cn"
    if install_parameters["partition"] == "aws-cn"
    else "opensearchservice.amazonaws.com"
)
_iam_iter = _iam_paginator.paginate(
    PathPrefix=f"/aws-service-role/{_opensearch_service_principal}"
)
```

作用：在 `aws-cn` 使用正确的 OpenSearch 服务主体后缀。

## 8. `installer/resources/user_data/controller/03_setup.sh.j2`

### Monaco 使用私有 npm registry（修改后行 71-76）

原始代码：
```bash
# Install required Node modules
${EDH_BOOTSTRAP_ASSETS_FOLDER}/node/bin/npm install --prefix "/opt/edh/{{ context.get("/configuration/ClusterId") }}/cluster_manager/web_interface/static" monaco-editor@0.52.0
```

修改后：
```bash
# Install required Node modules. npm_registry lets China/on-prem deployments
# use an approved internal registry instead of registry.npmjs.org.
NPM_REGISTRY="{{ context.get('/system/nodejs/npm_registry', '') }}"
NPM_ARGS=()
[[ -n "${NPM_REGISTRY}" ]] && NPM_ARGS+=(--registry "${NPM_REGISTRY}")
${EDH_BOOTSTRAP_ASSETS_FOLDER}/node/bin/npm install "${NPM_ARGS[@]}" --prefix "/opt/edh/{{ context.get("/configuration/ClusterId") }}/cluster_manager/web_interface/static" monaco-editor@0.52.0
```

作用：控制器安装 Monaco 时可走批准的 npm 源。

## 9. `source/soca/cluster_node_bootstrap/templates/linux/soca_python.sh.j2`

### Linux 节点 Python 私有源和 S3 wheelhouse（修改后行 164-180）

原始代码：
```bash
# --user to make sure python libs are installed in the SOCA_PYTHON path only (we don't touch system python)
if ! ${SOCA_PYTHON_LOCAL_INSTALL_PREFIX}/bin/pip3 install --user -r requirements.txt; then
    exit_fail "Unable to install SOCA Python requirements (see templates/linux/soca_python_requirements.txt.j2)"
fi
```

修改后：
```bash
# --user keeps packages inside the EDH Python path. A private index or
# an S3 wheelhouse avoids node bootstrap downloads from public PyPI.
local PIP_INDEX_URL="{{ context.get('/system/python/pip_index_url', '') }}"
local PIP_EXTRA_INDEX_URL="{{ context.get('/system/python/pip_extra_index_url', '') }}"
local PIP_WHEELHOUSE_S3_URI="{{ context.get('/system/python/pip_wheelhouse_s3_uri', '') }}"
local PIP_ARGS=()
if [[ -n "${PIP_WHEELHOUSE_S3_URI}" ]]; then
  local PIP_WHEELHOUSE_DIR="${EDH_BOOTSTRAP_ASSETS_FOLDER}/soca_python/wheelhouse"
  aws_cli s3 sync "${PIP_WHEELHOUSE_S3_URI}" "${PIP_WHEELHOUSE_DIR}" --quiet || exit_fail "Unable to download Python wheelhouse"
  PIP_ARGS+=(--no-index --find-links "${PIP_WHEELHOUSE_DIR}")
else
  [[ -n "${PIP_INDEX_URL}" ]] && PIP_ARGS+=(--index-url "${PIP_INDEX_URL}")
  [[ -n "${PIP_EXTRA_INDEX_URL}" ]] && PIP_ARGS+=(--extra-index-url "${PIP_EXTRA_INDEX_URL}")
fi
if ! ${SOCA_PYTHON_LOCAL_INSTALL_PREFIX}/bin/pip3 install --user "${PIP_ARGS[@]}" -r requirements.txt; then
    exit_fail "Unable to install SOCA Python requirements (see templates/linux/soca_python_requirements.txt.j2)"
fi
```

作用：节点依赖优先支持离线 S3 wheelhouse，否则使用私有 PyPI。

## 10. `source/soca/cluster_node_bootstrap/templates/windows/dcv/dcv_vdi_monitoring.ps.j2`

### 中国区 CloudWatch Agent URL（修改后行 17-21）

原始代码：
```powershell
$AwsRegion  = "{{ context.get('/configuration/Region') }}"
$ClusterId  = "{{ context.get('/configuration/ClusterId') }}"
$CwaUrl     = "https://amazoncloudwatch-agent-$($AwsRegion).s3.$($AwsRegion).amazonaws.com/windows/amd64/latest/amazon-cloudwatch-agent.msi"
```

修改后：
```powershell
$AwsRegion  = "{{ context.get('/configuration/Region') }}"
$ClusterId  = "{{ context.get('/configuration/ClusterId') }}"
$AwsDomainSuffix = if ($AwsRegion -like "cn-*") { "amazonaws.com.cn" } else { "amazonaws.com" }
$CwaUrl     = "https://amazoncloudwatch-agent-$($AwsRegion).s3.$($AwsRegion).$AwsDomainSuffix/windows/amd64/latest/amazon-cloudwatch-agent.msi"
```

作用：Windows DCV 节点在中国区使用 `.amazonaws.com.cn` 端点。

### Windows DCV monitoring 的 Python/boto3 离线化（修改后行 106-133）

原始代码：
```powershell
$PyVersion = "3.11.9"
$PyZipUrl  = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
$PyZip     = "$env:TEMP\python-embed.zip"
$PyExe     = "$CollectorPython\python.exe"

if (-not (Test-Path $PyExe)) {
    Log-Info -Message "Downloading Python $PyVersion embeddable for collector"
    Invoke-WebRequest -Uri $PyZipUrl -OutFile $PyZip -UseBasicParsing
    Expand-Archive -Path $PyZip -DestinationPath $CollectorPython -Force
    # Enable site-packages so pip-installed boto3 is importable
    $PthFile = Get-ChildItem $CollectorPython -Filter "python*._pth" | Select-Object -First 1
    if ($PthFile) {
        (Get-Content $PthFile.FullName) -replace '^#import site', 'import site' | Set-Content $PthFile.FullName -Encoding ASCII
    }
    # Bootstrap pip
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$env:TEMP\get-pip.py" -UseBasicParsing
    & $PyExe "$env:TEMP\get-pip.py" --quiet
    & $PyExe -m pip install --quiet boto3
}
```

修改后：
```powershell
$PyVersion = "3.11.9"
$PyZipUrl  = "{{ context.get('/system/windows_dcv_monitoring/python_embed_url') }}"
$GetPipUrl = "{{ context.get('/system/windows_dcv_monitoring/get_pip_url') }}"
$PipIndexUrl = "{{ context.get('/system/windows_dcv_monitoring/pip_index_url', '') }}"
$PipWheelhouseS3Uri = "{{ context.get('/system/windows_dcv_monitoring/pip_wheelhouse_s3_uri', '') }}"
$PyZip     = "$env:TEMP\python-embed.zip"
$PyExe     = "$CollectorPython\python.exe"

if (-not (Test-Path $PyExe)) {
    Log-Info -Message "Downloading Python $PyVersion embeddable for collector"
    Invoke-SOCAFileDownload -DownloadUrl $PyZipUrl -SaveAs $PyZip
    Expand-Archive -Path $PyZip -DestinationPath $CollectorPython -Force
    # Enable site-packages so pip-installed boto3 is importable
    $PthFile = Get-ChildItem $CollectorPython -Filter "python*._pth" | Select-Object -First 1
    if ($PthFile) {
        (Get-Content $PthFile.FullName) -replace '^#import site', 'import site' | Set-Content $PthFile.FullName -Encoding ASCII
    }
    # Install boto3 from an offline S3 wheelhouse or approved package index.
    $GetPipPath = "$env:TEMP\get-pip.py"
    Invoke-SOCAFileDownload -DownloadUrl $GetPipUrl -SaveAs $GetPipPath
    & $PyExe $GetPipPath --quiet
    if ($PipWheelhouseS3Uri) {
        $Wheelhouse = "$CollectorDir\wheelhouse"
        Invoke-SOCAAwsCli s3 sync $PipWheelhouseS3Uri $Wheelhouse --quiet
        & $PyExe -m pip install --quiet --no-index --find-links $Wheelhouse boto3
    } elseif ($PipIndexUrl) {
        & $PyExe -m pip install --quiet --index-url $PipIndexUrl boto3
    } else {
        & $PyExe -m pip install --quiet boto3
    }
}
```

作用：Windows DCV monitoring 支持资源镜像下载、私有 PyPI 和 S3 wheelhouse。

## 11. `installer/sync_cn_artifacts.py`（新增文件）

原始代码：文件不存在。

修改后（行 1-91）：
```python
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
```

作用：按宁夏覆盖配置选择 S3 目标，列举、校验并同步静态制品；`--dry-run` 只打印清单。

## 验证记录

- [x] 受修改影响的 Python 文件通过编辑器语义诊断。
- [x] `git diff --check` 通过。
- [x] `default_config.yml,config.cn-northwest-1.yml` 深度合并验证通过。
- [x] `sync_cn_artifacts.py --dry-run` 验证通过；不会下载或上传制品。
- [ ] 尚未使用宁夏账户执行 CDK synth、制品实际同步或真实部署。

## 12. `installer/region_map.d/aws/999-my-ami-defaults.yaml`

### 宁夏 RHEL 8 AMI 的 RegionMap 预检映射（修改后行 1-5）

原始代码：
```yaml
---

# Example AMI defaults for my local site
# Make sure to preserve proper YAML formatting/indention

#us-east-1:
#  x86_64:
#    amazonlinux2: ami-123
#us-east-2:
#  x86_64:
#    amazonlinux2: ami-456
```

修改后：
```yaml
---
# Site-local AMI defaults. cn-northwest-1 RHEL 8.10 AMI verified 2026-09-02.
cn-northwest-1:
  x86_64:
    rhel8: ami-00ccfc1b12bbbabfc
```

作用：`install_soca.py` 在进入 CDK 前会独立读取 `RegionMap.<region>.x86_64.<base_os>` 做基础 OS 可用性校验；该校验不读取 `Config.china_region.ami_overrides`。此映射使 `--base-os rhel8` 能通过宁夏预检，同时与 overlay 中的 AMI 保持一致。

## 13. `installer/resources/src/helpers/installer/helpers.py`

### 资源镜像跳过包管理目录 URL（修改后约行 947-964）

原始代码：
```python
if url.endswith(".git") or url.startswith("git://"):
    logger.info(f"Skipping git repository URL: {url}")
    return True
for excluded in MIRROR_EXCLUDE_URLS:
    if url.startswith(excluded):
        logger.info(f"Skipping excluded URL: {url}")
        return True
```

修改后：
```python
if url.endswith(".git") or url.startswith("git://"):
    logger.info(f"Skipping git repository URL: {url}")
    return True
# Package indexes and registries are directory endpoints, not artifacts.
# Mirroring them attempts to save a directory and fails with Errno 21.
if url.startswith(("http://", "https://")) and url.endswith("/"):
    logger.info(f"Skipping directory/index URL (not an artifact): {url}")
    return True
for excluded in MIRROR_EXCLUDE_URLS:
    if url.startswith(excluded):
        logger.info(f"Skipping excluded URL: {url}")
        return True
```

作用：`resources_mirroring()` 之前把 `pip_index_url` 和 `npm_registry` 一类以 `/` 结尾的索引目录当作文件下载，导致 `[Errno 21] Is a directory` 并终止安装。新规则会跳过所有 HTTP(S) 目录 URL；实际制品仍按原逻辑镜像和校验。

## `source/` 后续适配审计

本次目标不仅是 `cn-northwest-1` 的 CDK synth，还包括部署后 controller、login、compute 和可选 Windows/DCV 节点的 bootstrap。审计范围覆盖运行时端点、外部制品、包仓库和分区限定服务。

但要完成无境外依赖的节点实际部署，以下模板仍应在启用对应功能前改为受控 S3/内部仓库，或在自定义 AMI 中预置：

- [x] `source/soca/cluster_node_bootstrap/templates/windows/dcv/dcv_server.ps.j2`：VC++ Redistributable 已改为 `Parameters.system.dcv.windows.vc_redist_url` + `Invoke-SOCAFileDownload`。部署前须在 `<cn-artifact-bucket>` 预置该对象；生产建议固定版本并在 overlay 写入 SHA-256。
- [x] `source/soca/cluster_node_bootstrap/templates/windows/dcv/dcv_vdi_monitoring.ps.j2`：CloudWatch Agent 已改为 `Parameters.system.cloudwatch_agent.windows.url` + `Invoke-SOCAFileDownload`；宁夏 overlay 使用 `.amazonaws.com.cn` 原始地址，并由制品重写映射到 `<cn-artifact-bucket>`。
- [x] `source/soca/cluster_manager/web_interface/api/v1/cost_management/pricing.py`：已在 `cn-*` 直接关闭 Pricing API，避免控制面运行时调用硬编码的 `us-east-1`。
- [x] `source/soca/cluster_node_bootstrap/templates/linux/scheduler/openpbs/install.sh.j2:148-160`：宁夏安全默认值已将 OpenPBS 设为 `tgz`，不会执行默认的 `git clone` 分支。
- [x] `source/soca/cluster_node_bootstrap/templates/linux/shared_storage/mount_fsx_lustre.sh.j2`：宁夏已在安装参数阶段阻断 `fsx_lustre`，避免执行该模板的公共 FSx repo 下载。首轮使用 EFS。
- [ ] `source/soca/cluster_node_bootstrap/templates/linux/gpu/amd_drivers.sh.j2:30-59`：RHEL/Rocky AMD 驱动使用 `repo.radeon.com` 和递归 `wget`。启用 AMD GPU 前应改为内网 Yum repo 或宁夏 S3 内的固定 RPM，并保留校验。
- [ ] `source/soca/cluster_node_bootstrap/templates/linux/gpu/nvidia_drivers.sh.j2:120-123`：Tesla 驱动 URL 来自配置的公共 NVIDIA endpoint；应按批准的宁夏镜像地址覆盖或预置 AMI。
- [ ] `source/soca/cluster_node_bootstrap/templates/linux/common/file_download.sh.j2:66-105`：仍支持公共 HTTP 与 git fallback。这是通用能力；宁夏生产配置必须确保所有启用功能的 URL 已预置到 `<cn-artifact-bucket>` 或内部源，避免运行时落到 fallback。
- [ ] 基础 OS 的 DNF/Yum/APT 源不由 EDH 配置统一接管。RHEL 8 AMI 应在部署前确认其 RHUI/企业镜像可在宁夏子网访问；私有子网需要匹配的 VPC Endpoint、NAT 或内部软件仓库。

已确认受配置和现有制品机制覆盖的节点制品包括 Python、Node.js、OpenPBS/Slurm 依赖、OpenMPI、EFA、SSM、DCV、Windows VC++、Windows CloudWatch Agent 和常规 `Parameters.system.*` URL。当前 overlay 的安全默认值关闭 analytics、Batch 示例、USB remotization、DCV high-scale/pool/session-sharing 和 Global Accelerator；全部 FSx provider 在宁夏安装参数阶段阻断。AMD/NVIDIA GPU、基础 OS 包仓库和没有被改写的公共 fallback 仍不能视为已验证。

### 之前为什么没有发现

1. 之前的检查集中在代码是否存在 `aws-cn` 分区、S3 后缀、AMI overlay 和包源可配置项，未按安装器的实际执行顺序走到 `RegionMap` 基础 OS 预检，因此遗漏了“AMI 有两套来源”的不一致。
2. `rewrite_cn_artifact_urls()` 已对 `pip_index_url`/`npm_registry` 做 key 路径排除，导致静态审查误以为整个镜像流程已处理包源；实际 `resources_mirroring()` 使用独立的 URL 遍历和跳过规则，未复用该排除清单。
3. 没有在真实宁夏账户使用带实际 registry URL 的配置执行 install-host 制品镜像，所以未触发目录 URL 下载的 `Errno 21`。本次 synth 实测日志提供了该运行时证据。
4. 先前 `source/` 搜索范围偏向分区 ARN 和显式 AWS 端点，未按“是否绕过 Parameters/file_download”筛选 Windows VC++、FSx repo 与 AMD recursive wget 等功能性下载链路。

## 14. `installer/resources/src/install_soca.py`

### 尊重宁夏 overlay 的资源镜像开关（修改后约行 266-276）

原始代码：
```python
mirror_config = config.setdefault("services", {}).setdefault(
    "resources_mirroring", {}
)
mirror_config.update({"enabled": True, "method": "install-host", "failure_mode": "hard"})
```

修改后：
```python
mirror_config = config.setdefault("services", {}).setdefault(
    "resources_mirroring", {}
)
# Keep an operator's explicit enabled:false, e.g. when all approved
# artifacts are already present under china_region.artifact_base_uri. The
# commercial default is method=ask; use install-host instead in Ningxia so
# unattended installs never block on an interactive mirror prompt.
mirror_config.setdefault("enabled", True)
if mirror_config.get("method") in (None, "ask"):
    mirror_config["method"] = "install-host"
if mirror_config.get("failure_mode") in (None, "soft"):
    mirror_config["failure_mode"] = "hard"
```

作用：宁夏 overlay 的 `resources_mirroring.enabled: false` 不再被安全默认值改回 `true`。部署会直接消费预置于 `s3://<cn-artifact-bucket>/edh/artifacts` 的制品；只有未显式配置时，宁夏才默认选择 install-host + hard failure。

### 所有 FSx 客户端风险的宁夏部署保护（修改后约行 1448-1461）

原始代码：无宁夏专用检查，任意文件系统 provider 会直接进入参数校验和后续 bootstrap。

修改后：
```python
if install_parameters.get("region") == "cn-northwest-1":
    _unsupported_filesystems = {"fsx_lustre", "fsx_ontap", "fsx_openzfs"}
    _selected_providers = {
        install_parameters.get("fs_apps_provider"),
        install_parameters.get("fs_data_provider"),
    }
    if _unsupported_filesystems & _selected_providers:
        logger.error(
            "FSx providers are disabled for cn-northwest-1 until their regional "
            "availability and offline client repositories are verified. Use EFS or "
            "pass a separately validated implementation."
        )
        sys.exit(1)
```

作用：避免用户在宁夏直接启用未经验证的任意 FSx provider。FSx Lustre bootstrap 存在公共 repo 下载；ONTAP 和 OpenZFS 的区域能力、客户端和部署参数也尚未在当前基线验证。首轮部署应使用 EFS。

## 15. `installer/default_config.yml`、`source/.../windows/dcv/dcv_server.ps.j2`

### Windows DCV 的 VC++ 运行库进入配置和镜像链路

原始代码（`dcv_server.ps.j2`）：
```powershell
Log-Info -Message "Microsoft Visual C++ 2022 not found, installing it ..."
Invoke-WebRequest -uri https://aka.ms/vs/17/release/vc_redist.x64.exe -OutFile "$EDHBootstrapAssetsFolder\vc_redist_64.exe"
& "$EDHBootstrapAssetsFolder\vc_redist_64.exe" /install /passive /norestart
```

修改后（模板）：
```powershell
$VcRedistUrl = "{{ context.get("/system/dcv/windows/vc_redist_url") }}"
$VcRedistSha = "{{ context.get("/system/dcv/windows/vc_redist_sha256", "") }}"
$VcRedistPath = "$EDHBootstrapAssetsFolder\vc_redist_64.exe"
Log-Info -Message "Microsoft Visual C++ 2022 not found, installing from $VcRedistUrl"
Invoke-SOCAFileDownload -DownloadUrl $VcRedistUrl -SaveAs $VcRedistPath -Sha256Checksum $VcRedistSha
& $VcRedistPath /install /passive /norestart
```

新增配置（`default_config.yml` 的 `Parameters.system.dcv.windows`）：
```yaml
vc_redist_url: "https://aka.ms/vs/17/release/vc_redist.x64.exe"
vc_redist_sha256: "" # Set a verified hash when overriding this URL with a private S3 artifact.
```

作用：Windows DCV 节点不再绕过 `Invoke-SOCAFileDownload`。宁夏部署时，该 URL 会由静态制品重写为 `<cn-artifact-bucket>` 下的对象；推荐预置固定版本并在 overlay 中配置 SHA-256。

## 16. `installer/default_config.yml`、`installer/config.cn-northwest-1.yml`、`source/.../windows/dcv/dcv_vdi_monitoring.ps.j2`

### Windows CloudWatch Agent 进入宁夏制品链路

原始代码：
```powershell
$AwsDomainSuffix = if ($AwsRegion -like "cn-*") { "amazonaws.com.cn" } else { "amazonaws.com" }
$CwaUrl = "https://amazoncloudwatch-agent-$($AwsRegion).s3.$($AwsRegion).$AwsDomainSuffix/windows/amd64/latest/amazon-cloudwatch-agent.msi"
...
Invoke-WebRequest -Uri $CwaUrl -OutFile $CwaMsi -UseBasicParsing
```

修改后：
```powershell
$CwaUrl = "{{ context.get('/system/cloudwatch_agent/windows/url') }}".Replace("%region%", $AwsRegion)
$CwaSha = "{{ context.get('/system/cloudwatch_agent/windows/sha256', '') }}"
...
Invoke-SOCAFileDownload -DownloadUrl $CwaUrl -SaveAs $CwaMsi -Sha256Checksum $CwaSha
```

新增默认配置：
```yaml
cloudwatch_agent:
  windows:
    url: "https://amazoncloudwatch-agent-%region%.s3.%region%.amazonaws.com/windows/amd64/latest/amazon-cloudwatch-agent.msi"
    sha256: ""
```

宁夏 overlay 覆盖为：
```yaml
cloudwatch_agent:
  windows:
    url: "https://amazoncloudwatch-agent-cn-northwest-1.s3.cn-northwest-1.amazonaws.com.cn/windows/amd64/latest/amazon-cloudwatch-agent.msi"
    sha256: ""
```

作用：Windows VDI 节点通过统一下载器支持 `s3://mirror|https://fallback`，并在宁夏由制品重写机制映射到 `<cn-artifact-bucket>`。`latest` 包是滚动版本，当前不填 hash；生产应固定版本、预置 S3 对象并填写经验证 SHA-256。

## 17. `source/soca/cluster_manager/web_interface/api/v1/cost_management/pricing.py`

### 中国区关闭不可用的 Pricing API

原始代码：
```python
if _region.startswith("us-gov-"):
    return SocaResponse(
        success=False,
        message=_("Cost estimation is not available in the GovCloud partition (the AWS Pricing API is not offered in aws-us-gov)."),
    ).as_flask()
```

修改后：
```python
if _region.startswith(("us-gov-", "cn-")):
    return SocaResponse(
        success=False,
        message=_(
            "Cost estimation is not available in the AWS GovCloud or China partitions "
            "because the AWS Pricing API is not available there."
        ),
    ).as_flask()
```

作用：成本估算 API 之前会从 `us-east-1` 创建 Pricing client；该服务不适用于中国区。现在返回明确的功能不可用响应，不影响集群核心功能、作业提交或节点管理。

## 运行时部署结论（更新）

- 已处理：中国区 S3 后缀、静态制品 S3 重写、RegionMap + overlay AMI、Linux/Windows Python 国内源、npm 国内源、Lambda layer 私有 PyPI、Windows DCV 的 VC++ 和 CloudWatch Agent 下载链路、Pricing API 分区保护、资源镜像目录 URL、FSx 未验证能力阻断。
- 首轮可运行基线：`--base-os rhel8`、EFS、SQLite、OpenPBS tarball、`resources_mirroring.enabled: false`，并在部署前将全部改写后的静态制品预置到 `s3://<cn-artifact-bucket>/edh/artifacts`。使用 S3 Gateway Endpoint；若不提供 NAT，则还需按已启用 AWS API 服务建立 Interface Endpoint。
- 仍必须实机预检后才可启用：任何 FSx provider、AMD/NVIDIA GPU、Windows/DCV、Batch、analytics/OpenSearch、Aurora Serverless v2、AI Assistant。它们分别依赖中国区服务可用性、特定 AMI/实例供给、系统包仓库或独立外部制品。

### 宁夏实机运行验证矩阵

静态代码检查只能证明已启用路径不会明显使用商业区硬编码端点或未受控的下载器，不能证明目标账号中所有服务、AMI、实例规格和软件仓库均可用。以下验证必须在 `cn-northwest-1` 的部署机与新建节点上执行：

1. 使用当前 overlay 以 `--base-os rhel8 --fs-apps-provider efs --fs-data-provider efs --cdk-cmd synth` 验证 RegionMap、AMI、分区、Lambda layer 和 CDK 模板。
2. 部署前将 overlay 中的 `<cn-artifact-bucket>` 替换为实际宁夏桶，再运行 `python installer/sync_cn_artifacts.py --config installer/default_config.yml,installer/config.cn-northwest-1.yml --region cn-northwest-1 --dry-run`；确认清单内每个对象都已存在于该桶的 `edh/artifacts/` 前缀，然后以 hash 校验实际对象。
3. 用最小配置部署 controller/login/一个 compute 节点；验证节点 boot 日志中没有访问 `python.org`、GitHub、Node.js、CloudFront、PyPI、npmjs、aka.ms、公共 FSx repo、AMD/NVIDIA repo 的 fallback。
4. 在 RHEL 8 节点执行系统包安装、Python requirements、OpenPBS tgz、SSM Agent、DCV（若启用）和 EFS mount 的端到端验证。私有子网须验证 S3 Gateway Endpoint、SSM/EC2/CloudWatch/Secrets Manager 等已启用服务的 Interface Endpoint 或经批准 NAT。
5. 仅在该最小集稳定后，逐项单独开启 Windows/DCV、GPU、FSx、Aurora、OpenSearch、Batch 和 AI Assistant；每项都先执行区域 API/服务目录预检，再启动实际节点。
