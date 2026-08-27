"""
NTP 客戶端模組 (ntp_client.py)
實作標準 RFC 5905 NTP/SNTP 客戶端通訊協定
提供高精確度時間取得、網路延遲補償與時間位移 (Offset) 計算
"""

import socket
import struct
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# NTP 紀元 (1900-01-01) 與 Unix 紀元 (1970-01-01) 之秒數差
NTP_DELTA = 2208988800

# 預設推薦之優質 NTP 伺服器清單
DEFAULT_NTP_SERVERS = [
    {
        "name": "台灣標準時間 (拓克 tock)",
        "host": "tock.stdtime.gov.tw",
        "region": "台灣國家時間與頻率標準實驗室",
    },
    {
        "name": "台灣標準時間 (提克 tick)",
        "host": "tick.stdtime.gov.tw",
        "region": "台灣國家時間與頻率標準實驗室",
    },
    {
        "name": "台灣標準時間 (time.stdtime)",
        "host": "time.stdtime.gov.tw",
        "region": "台灣國家時間與頻率標準實驗室",
    },
    {
        "name": "Google NTP (time.google.com)",
        "host": "time.google.com",
        "region": "全球 Anycast (Google)",
    },
    {
        "name": "Cloudflare NTP (time.cloudflare.com)",
        "host": "time.cloudflare.com",
        "region": "全球 Anycast (Cloudflare)",
    },
    {
        "name": "微軟官方 NTP (time.windows.com)",
        "host": "time.windows.com",
        "region": "全球 Anycast (Microsoft)",
    },
    {
        "name": "台灣 NTP 伺服器池 (tw.pool.ntp.org)",
        "host": "tw.pool.ntp.org",
        "region": "NTP Pool Project (台灣節點)",
    },
    {
        "name": "全球 NTP 伺服器池 (pool.ntp.org)",
        "host": "pool.ntp.org",
        "region": "NTP Pool Project (全球池)",
    },
]


def _system_to_ntp_timestamp(ts: float) -> Tuple[int, int]:
    """將 Unix timestamp (秒) 轉換為 NTP 的 64 位元時間戳 (整數秒, 小數部分)"""
    ntp_ts = ts + NTP_DELTA
    sec = int(ntp_ts)
    frac = int((ntp_ts - sec) * (2**32))
    return sec, frac


def _ntp_to_system_timestamp(sec: int, frac: int) -> float:
    """將 NTP 的 64 位元時間戳轉換為 Unix timestamp (秒)"""
    return (sec + (frac / (2**32))) - NTP_DELTA


class NTPClient:
    """NTP / SNTP 通訊協定客戶端"""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    def query(self, host: str, port: int = 123) -> Dict:
        """
        向指定的 NTP 伺服器查詢時間並計算網路延遲與時間誤差

        :param host: NTP 伺服器位址 (域名或 IP)
        :param port: NTP 伺服器連接埠 (預設 123)
        :return: 包含查詢結果之字典
        """
        # 建立 48 位元組 NTP 請求封包
        # LI=0, VN=4 (NTPv4), Mode=3 (Client) => 0x23 (00 100 011)
        req_header = 0x23
        packet = bytearray(48)
        packet[0] = req_header

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_sock.settimeout(self.timeout)

        try:
            # 記錄發送時的本地時間 t1 (Unix Timestamp)
            t1 = time.time()
            sec, frac = _system_to_ntp_timestamp(t1)
            # 將 t1 填入 Transmit Timestamp 欄位 (byte 40~47)
            struct.pack_into("!II", packet, 40, sec, frac)

            # 發送 NTP 請求
            client_sock.sendto(packet, (host, port))

            # 接收回應
            data, addr = client_sock.recvfrom(512)
            # 記錄接收時的本地時間 t4 (Unix Timestamp)
            t4 = time.time()

            if len(data) < 48:
                raise ValueError(f"收到不完整的 NTP 封包 (長度: {len(data)})")

            # 解析 NTP 封包
            # 第一個位元組：LI (2b), VN (3b), Mode (3b)
            li_vn_mode = data[0]
            stratum = data[1]
            poll = data[2]
            precision = struct.unpack("!b", data[3:4])[0]

            # 接收時間戳 Receive Timestamp t2 (byte 32~39)
            t2_sec, t2_frac = struct.unpack("!II", data[32:40])
            t2 = _ntp_to_system_timestamp(t2_sec, t2_frac)

            # 傳送時間戳 Transmit Timestamp t3 (byte 40~47)
            t3_sec, t3_frac = struct.unpack("!II", data[40:48])
            t3 = _ntp_to_system_timestamp(t3_sec, t3_frac)

            # 計算往返延遲 (Round-Trip Delay) 與 時間位移 (Offset)
            # RFC 5905 公式:
            # Delay = (t4 - t1) - (t3 - t2)
            # Offset = ((t2 - t1) + (t3 - t4)) / 2
            delay = (t4 - t1) - (t3 - t2)
            offset = ((t2 - t1) + (t3 - t4)) / 2

            # 校正後的精確 Unix timestamp
            # 當前精準 UTC 時間 = t4 + offset
            corrected_utc_ts = t4 + offset
            corrected_utc_dt = datetime.fromtimestamp(
                corrected_utc_ts, tz=timezone.utc
            )
            corrected_local_dt = datetime.fromtimestamp(corrected_utc_ts)

            return {
                "success": True,
                "server": host,
                "server_ip": addr[0],
                "stratum": stratum,
                "precision": precision,
                "delay_ms": round(delay * 1000, 3),
                "offset_ms": round(offset * 1000, 3),
                "offset_sec": offset,
                "t1": t1,
                "t2": t2,
                "t3": t3,
                "t4": t4,
                "corrected_utc_dt": corrected_utc_dt,
                "corrected_local_dt": corrected_local_dt,
                "corrected_ts": corrected_utc_ts,
                "error": None,
            }

        except socket.timeout:
            return {
                "success": False,
                "server": host,
                "error": f"連線至 NTP 伺服器 '{host}' 逾時 (超過 {self.timeout} 秒)",
            }
        except socket.gaierror as e:
            return {
                "success": False,
                "server": host,
                "error": f"DNS 解析失敗，找不到伺服器 '{host}': {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "server": host,
                "error": f"查詢失敗: {str(e)}",
            }
        finally:
            client_sock.close()

    def query_with_fallback(self, servers: List[str]) -> Dict:
        """
        依序嘗試伺服器清單，若失敗則自動切換至下一台備援伺服器

        :param servers: NTP 伺服器主機名稱列表
        :return: 第一台成功查詢的結果，或最後一次失敗的結果
        """
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
            "error": "未提供任何有效的 NTP 伺服器位址",
        }

    def test_server(self, host: str) -> Dict:
        """
        測試指定 NTP 伺服器的可用性與連線延遲 (Ping)

        :param host: 伺服器主機名稱
        :return: 包含延遲與狀態的測試結果
        """
        result = self.query(host)
        if result.get("success"):
            return {
                "success": True,
                "server": host,
                "server_ip": result.get("server_ip"),
                "delay_ms": result.get("delay_ms"),
                "offset_ms": result.get("offset_ms"),
                "stratum": result.get("stratum"),
                "message": f"連線成功！延遲: {result.get('delay_ms')} ms，誤差: {result.get('offset_ms')} ms (Stratum {result.get('stratum')})",
            }
        else:
            return {
                "success": False,
                "server": host,
                "message": f"連線失敗: {result.get('error')}",
            }
