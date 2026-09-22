"""
HTTPS 時間客戶端模組 (http_time_client.py)
當網路環境 (如企業嚴格防火牆或網管) 封鎖對外 UDP Port 123 (NTP) 時，
透過標準 HTTPS (TCP 443) 向各大高可用性雲端伺服器請求 HTTP 標頭中的 Date 欄位，
結合網路往返延遲 (RTT / 2) 進行高精度時間補償與校時。
完全採用 Python 內建標準庫，零第三方套件相依。
"""

import email.utils
import http.client
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

# 預設推薦之優質 HTTPS 備援時間伺服器清單
DEFAULT_HTTP_SERVERS = [
    {
        "name": "Google (www.google.com)",
        "host": "www.google.com",
        "region": "全球 Anycast (Google)",
    },
    {
        "name": "Cloudflare (www.cloudflare.com)",
        "host": "www.cloudflare.com",
        "region": "全球 Anycast (Cloudflare)",
    },
    {
        "name": "微軟官方 (www.microsoft.com)",
        "host": "www.microsoft.com",
        "region": "全球 Anycast (Microsoft)",
    },
    {
        "name": "蘋果官方 (www.apple.com)",
        "host": "www.apple.com",
        "region": "全球 Anycast (Apple)",
    },
]


class HTTPTimeClient:
    """HTTPS (TCP 443) 備援時間同步客戶端"""

    def __init__(self, timeout: float = 3.5):
        self.timeout = timeout
        # 建立寬鬆相容的 SSL 上下文 (針對僅需讀取 Header 的校時需求)
        try:
            self.ssl_context = ssl.create_default_context()
        except Exception:
            self.ssl_context = None

    def query(self, host: str, port: int = 443) -> Dict:
        """
        向指定的 HTTPS 伺服器發送 HEAD 請求，解析 Date 標頭並計算網路延遲與時間位移

        :param host: 伺服器主機名稱 (例如 www.google.com)
        :param port: 連接埠 (預設 443)
        :return: 包含查詢結果之字典 (相容 NTPClient 輸出結構)
        """
        host = host.strip()
        # 若傳入包含 http:// 或 https://，自動去除
        if host.startswith("https://"):
            host = host[8:]
        elif host.startswith("http://"):
            host = host[7:]
        # 去除結尾路徑斜線
        if "/" in host:
            host = host.split("/")[0]

        conn = None
        try:
            # 建立 HTTPS 連線
            if self.ssl_context:
                conn = http.client.HTTPSConnection(
                    host, port=port, timeout=self.timeout, context=self.ssl_context
                )
            else:
                conn = http.client.HTTPSConnection(host, port=port, timeout=self.timeout)

            # 記錄請求發送前的本地時間 t1
            t1 = time.time()

            # 發送 HEAD 請求 (僅獲取 Header，耗費流量低於 1KB)
            conn.request("HEAD", "/", headers={"User-Agent": "WindowsTimeAutoUpdate/1.0"})

            # 接收回應
            resp = conn.getresponse()

            # 記錄回應接收後的本地時間 t2
            t2 = time.time()

            # 取得遠端伺服器 IP (若可用)
            server_ip = None
            try:
                if conn.sock:
                    peer = conn.sock.getpeername()
                    server_ip = peer[0] if isinstance(peer, tuple) else str(peer)
            except Exception:
                server_ip = host

            # 讀取 Date 標頭
            date_header = resp.getheader("Date")
            if not date_header:
                raise ValueError(f"伺服器 '{host}' 回應中未包含標準 Date 標頭")

            # 解析 HTTP Date 標頭 (RFC 2822 / RFC 7231)
            # 例如: "Tue, 22 Sep 2026 02:56:41 GMT"
            remote_dt = email.utils.parsedate_to_datetime(date_header)
            if remote_dt.tzinfo is None:
                remote_dt = remote_dt.replace(tzinfo=timezone.utc)
            else:
                remote_dt = remote_dt.astimezone(timezone.utc)

            # HTTP Date 是整數秒。因此伺服器生成 Date 時的實際時間平均落在 [sec, sec + 1) 間
            # 平均基準點約為 remote_dt.timestamp() + 0.5 秒
            # 往返延遲 RTT = t2 - t1
            rtt = max(0.0, t2 - t1)
            # 單向估計延遲約為 RTT / 2
            half_rtt = rtt / 2.0

            # 校正後精準 UTC 時間戳 (伺服器時間基準 + 估計傳輸耗時)
            corrected_utc_ts = remote_dt.timestamp() + 0.5 + half_rtt
            corrected_utc_dt = datetime.fromtimestamp(
                corrected_utc_ts, tz=timezone.utc
            )
            corrected_local_dt = datetime.fromtimestamp(corrected_utc_ts)

            # 時間位移 Offset = 校正後時間 - 本地當前時間 t2
            offset = corrected_utc_ts - t2

            return {
                "success": True,
                "protocol": "HTTPS",
                "server": host,
                "server_ip": server_ip or host,
                "stratum": 2,  # 標記為 Stratum 2 備援級別
                "delay_ms": round(rtt * 1000, 3),
                "offset_ms": round(offset * 1000, 3),
                "offset_sec": offset,
                "t1": t1,
                "t2": t2,
                "corrected_utc_dt": corrected_utc_dt,
                "corrected_local_dt": corrected_local_dt,
                "corrected_ts": corrected_utc_ts,
                "error": None,
            }

        except socket.timeout:
            return {
                "success": False,
                "protocol": "HTTPS",
                "server": host,
                "error": f"連線至 HTTPS 伺服器 '{host}' 逾時 (超過 {self.timeout} 秒)",
            }
        except socket.gaierror as e:
            return {
                "success": False,
                "protocol": "HTTPS",
                "server": host,
                "error": f"DNS 解析失敗，找不到伺服器 '{host}': {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "protocol": "HTTPS",
                "server": host,
                "error": f"HTTPS 時間查詢失敗: {str(e)}",
            }
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def query_with_fallback(self, servers: Optional[List[str]] = None) -> Dict:
        """
        依序嘗試 HTTPS 備援伺服器清單，若失敗則自動切換至下一台

        :param servers: 伺服器主機名稱列表 (若為 None 則使用預設清單)
        :return: 第一台成功查詢的結果，或最後一次失敗的結果
        """
        if not servers:
            servers = [s["host"] for s in DEFAULT_HTTP_SERVERS]

        last_result = None
        for s in servers:
            s = s.strip()
            if not s:
                continue
            result = self.query(s)
            if result.get("success"):
                return result
            last_result = result

        if last_result is not None:
            return last_result

        return {
            "success": False,
            "protocol": "HTTPS",
            "error": "未提供任何有效的 HTTPS 備援伺服器位址",
        }

    def test_server(self, host: str) -> Dict:
        """
        測試指定 HTTPS 伺服器的可用性與連線延遲

        :param host: 伺服器主機名稱
        :return: 包含延遲與狀態的測試結果
        """
        result = self.query(host)
        if result.get("success"):
            return {
                "success": True,
                "protocol": "HTTPS",
                "server": host,
                "server_ip": result.get("server_ip"),
                "delay_ms": result.get("delay_ms"),
                "offset_ms": result.get("offset_ms"),
                "message": (
                    f"HTTPS 連線成功！延遲: {result.get('delay_ms')} ms，"
                    f"時間誤差: {result.get('offset_ms')} ms"
                ),
            }
        else:
            return {
                "success": False,
                "protocol": "HTTPS",
                "server": host,
                "message": f"HTTPS 連線失敗: {result.get('error')}",
            }
