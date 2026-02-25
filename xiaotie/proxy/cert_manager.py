"""SSL 证书管理

生成和管理代理服务器所需的 CA 证书和服务器证书。
支持自动生成自签名 CA、导出证书供设备安装。
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 默认证书存储目录
DEFAULT_CERT_DIR = Path.home() / ".xiaotie" / "certs"


class CertManager:
    """SSL 证书管理器

    管理 mitmproxy 使用的 CA 证书。支持自动生成、
    查找已有证书、导出供移动设备安装。

    Args:
        cert_dir: 证书存储目录，默认 ~/.xiaotie/certs
    """

    def __init__(self, cert_dir: Optional[str | Path] = None):
        self.cert_dir = Path(cert_dir) if cert_dir else DEFAULT_CERT_DIR
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ca_cert_path(self) -> Path:
        """CA 证书路径 (PEM)"""
        return self.cert_dir / "mitmproxy-ca-cert.pem"

    @property
    def ca_key_path(self) -> Path:
        """CA 私钥路径"""
        return self.cert_dir / "mitmproxy-ca.pem"

    @property
    def ca_cert_p12(self) -> Path:
        """CA 证书 PKCS12 格式（iOS 安装用）"""
        return self.cert_dir / "mitmproxy-ca-cert.p12"

    @property
    def ca_cert_cer(self) -> Path:
        """CA 证书 CER 格式（Android 安装用）"""
        return self.cert_dir / "mitmproxy-ca-cert.cer"

    def has_ca(self) -> bool:
        """检查 CA 证书是否已存在"""
        return self.ca_cert_path.exists() and self.ca_key_path.exists()

    def ensure_ca(self) -> bool:
        """确保 CA 证书存在

        如果 mitmproxy 的默认证书目录有证书，复制过来。
        否则 mitmproxy 首次启动时会自动生成。

        Returns:
            bool: CA 证书是否就绪
        """
        if self.has_ca():
            return True

        # 尝试从 mitmproxy 默认目录复制
        mitm_dir = Path.home() / ".mitmproxy"
        if (mitm_dir / "mitmproxy-ca-cert.pem").exists():
            for name in ("mitmproxy-ca-cert.pem", "mitmproxy-ca.pem",
                         "mitmproxy-ca-cert.p12", "mitmproxy-ca-cert.cer"):
                src = mitm_dir / name
                if src.exists():
                    shutil.copy2(src, self.cert_dir / name)
            logger.info("已从 ~/.mitmproxy 复制 CA 证书")
            return True

        # mitmproxy 会在首次启动时自动生成
        logger.info("CA 证书将在代理首次启动时自动生成")
        return False

    def get_install_instructions(self, proxy_host: str = "127.0.0.1",
                                  proxy_port: int = 8080) -> str:
        """获取证书安装说明

        Args:
            proxy_host: 代理服务器地址
            proxy_port: 代理服务器端口

        Returns:
            格式化的安装说明文本
        """
        cert_path = self.ca_cert_path if self.has_ca() else "<代理启动后自动生成>"

        return (
            "=== SSL 证书安装说明 ===\n\n"
            f"CA 证书路径: {cert_path}\n\n"
            "方式一: 通过浏览器安装\n"
            f"  1. 配置设备代理为 {proxy_host}:{proxy_port}\n"
            "  2. 浏览器访问 http://mitm.it\n"
            "  3. 选择对应平台下载并安装证书\n\n"
            "方式二: 手动安装\n"
            "  iOS:\n"
            f"    1. 将 {self.ca_cert_path} 通过 AirDrop 发送到设备\n"
            "    2. 设置 -> 通用 -> VPN与设备管理 -> 安装描述文件\n"
            "    3. 设置 -> 通用 -> 关于本机 -> 证书信任设置 -> 启用\n\n"
            "  Android:\n"
            f"    1. 将 {self.ca_cert_cer} 复制到设备\n"
            "    2. 设置 -> 安全 -> 加密与凭据 -> 安装证书\n\n"
            "  macOS:\n"
            f"    sudo security add-trusted-cert -d -r trustRoot "
            f"-k /Library/Keychains/System.keychain {self.ca_cert_path}\n"
        )

    def export_cert(self, dest: str | Path, fmt: str = "pem") -> Path:
        """导出 CA 证书到指定路径

        Args:
            dest: 目标路径
            fmt: 格式 - pem, p12, cer

        Returns:
            导出的文件路径
        """
        dest = Path(dest).resolve()
        src_map = {
            "pem": self.ca_cert_path,
            "p12": self.ca_cert_p12,
            "cer": self.ca_cert_cer,
        }
        src = src_map.get(fmt)
        if src is None:
            raise ValueError(f"不支持的格式: {fmt}，可选: pem, p12, cer")
        if not src.exists():
            raise FileNotFoundError(f"证书文件不存在: {src}，请先启动代理生成证书")

        shutil.copy2(src, dest)
        logger.info("已导出证书到 %s (格式: %s)", dest, fmt)
        return dest

    def get_confdir(self) -> str:
        """获取 mitmproxy confdir 参数值"""
        return str(self.cert_dir)
