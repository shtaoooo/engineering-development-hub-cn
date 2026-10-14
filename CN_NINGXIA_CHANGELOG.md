# 宁夏区（cn-northwest-1）改造代码对照清单

> 基线：当前 Git `HEAD`。行号为修改后工作区行号。新增文件或新增代码块的“原始代码”标记为“无”。
>
> 本文覆盖宁夏适配涉及的全部工作区改动；`.kiro/` 不属于运行时代码，未纳入。

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
# Ningxia overlay. Do not put credentials in this file.
# Use with: --config installer/default_config.yml,installer/config.cn-northwest-1.yml
# Public China mirrors are used for Python and npm. Use a private mirror in regulated environments.
Config:
  china_region:
    safe_defaults_enabled: true
    artifact_base_uri: "s3://nwcd-solutions/edh/artifacts"
    # AMI IDs are account/region scoped. Leave empty until a real AMI is verified.
    ami_overrides: {}
  lambda_layers:
    pip_index_url: "https://mirrors.aliyun.com/pypi/simple/"
    pip_extra_index_url: ""
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

作用：提供单独的宁夏覆盖层，使用实际的阿里云 PyPI 和 npmmirror npm 公共镜像。S3 wheelhouse 为空时，节点会回退到已配置的 PyPI 镜像。

待处理：AMI ID 是目标宁夏账户和区域专属资源，无法从代码仓库可靠推导；保持空映射可确保在未验证 AMI 时部署被明确阻断，而不会使用伪造 ID。

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
