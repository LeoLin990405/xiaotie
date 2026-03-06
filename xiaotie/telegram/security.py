from __future__ import annotations

import hmac
import ipaddress
from typing import Iterable, Optional


def verify_secret_token(provided: Optional[str], expected: Optional[str]) -> bool:
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def verify_source_ip(client_ip: str, allowed_cidrs: Optional[Iterable[str]]) -> bool:
    if not allowed_cidrs:
        return True
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for cidr in allowed_cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if ip_obj in network:
            return True
    return False
