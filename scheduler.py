"""
背景定時排程模組 (scheduler.py)
負責管理自訂更新頻率、倒數計時計算、定時觸發同步回呼，並提供完全非阻塞的背景線程運行。
注意：排程內部全面採用單調時鐘 (time.monotonic)，避免受 Windows 系統時鐘調整、跳動或校時影響。
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Union
from time_syncer import TimeSyncer

# 頻率單位轉換為秒數之倍率字典
UNIT_MULTIPLIERS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
}


class TimeSyncScheduler:
    """自動時間同步排程器 (基於 time.monotonic 單調時鐘)"""

    def __init__(
        self,
        syncer: TimeSyncer,
        interval_value: int = 30,
        interval_unit: str = "minutes",
        server_provider: Optional[Callable[[], Union[str, List[str]]]] = None,
        threshold_provider: Optional[Callable[[], Optional[float]]] = None,
        on_sync_start: Optional[Callable[[], None]] = None,
        on_sync_finish: Optional[Callable[[Dict], None]] = None,
        on_tick: Optional[Callable[[float, str], None]] = None,
    ):
        """
        初始化排程器

        :param syncer: TimeSyncer 實例
        :param interval_value: 間隔數值 (預設 30)
        :param interval_unit: 間隔單位 ("seconds", "minutes", "hours", "days", 預設 "minutes")
        :param server_provider: 回傳目前選擇之 NTP 伺服器 (單一或列表) 的回呼函式
        :param threshold_provider: 回傳目前設定之誤差閾值 (秒數，若無則為 None) 的回呼函式
        :param on_sync_start: 同步即將開始時觸發的回呼
        :param on_sync_finish: 同步完成時觸發的回呼 (帶入同步結果字典)
        :param on_tick: 每秒倒數計時觸發的回呼 (帶入剩餘秒數與格式化字串)
        """
        self.syncer = syncer
        self.interval_value = max(1, interval_value)
        self.interval_unit = (
            interval_unit if interval_unit in UNIT_MULTIPLIERS else "minutes"
        )
        self.server_provider = server_provider
        self.threshold_provider = threshold_provider

        self.on_sync_start = on_sync_start
        self.on_sync_finish = on_sync_finish
        self.on_tick = on_tick

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_syncing = False

        # 使用 time.monotonic() 作為基準，不受系統時鐘調整影響
        self._next_sync_mono: Optional[float] = None
        self._last_sync_time: Optional[datetime] = None
        self._last_result: Optional[Dict] = None

    @property
    def interval_seconds(self) -> int:
        """取得目前設定的間隔總秒數"""
        multiplier = UNIT_MULTIPLIERS.get(self.interval_unit, 60)
        return max(1, int(self.interval_value * multiplier))

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_syncing(self) -> bool:
        return self._is_syncing

    def update_interval(self, value: int, unit: str):
        """動態更新同步頻率設定"""
        with self._lock:
            self.interval_value = max(1, value)
            if unit in UNIT_MULTIPLIERS:
                self.interval_unit = unit
            # 重新計算下次同步單調時間戳
            if self._running and not self._paused:
                self._next_sync_mono = time.monotonic() + self.interval_seconds

    def start(self, sync_immediately: bool = False):
        """啟動背景排程線程"""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._paused = False
            self._stop_event.clear()

            if sync_immediately:
                self._next_sync_mono = time.monotonic()
            else:
                self._next_sync_mono = time.monotonic() + self.interval_seconds

            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="TimeSyncSchedulerThread"
            )
            self._thread.start()

    def stop(self):
        """停止背景排程"""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def pause(self):
        """暫停排程"""
        with self._lock:
            self._paused = True

    def resume(self):
        """恢復排程"""
        with self._lock:
            self._paused = False
            self._next_sync_mono = time.monotonic() + self.interval_seconds

    def trigger_now_async(self, force: bool = True):
        """
        手動非同步立即觸發一次同步
        
        :param force: 是否強制寫入系統時間 (忽略閾值判斷，預設 True)
        """
        def _do_manual_sync():
            self._perform_sync(ignore_threshold=force)
            with self._lock:
                if self._running and not self._paused:
                    self._next_sync_mono = time.monotonic() + self.interval_seconds

        t = threading.Thread(
            target=_do_manual_sync, daemon=True, name="ManualSyncThread"
        )
        t.start()

    def get_remaining_seconds(self) -> float:
        """取得距離下次同步的剩餘物理秒數 (基於單調時鐘)"""
        if not self._running or self._paused or self._next_sync_mono is None:
            return 0.0
        now_mono = time.monotonic()
        rem = self._next_sync_mono - now_mono
        return max(0.0, rem)

    def get_remaining_formatted(self) -> str:
        """格式化剩餘時間為字串 (例如: '01:23:45' 或 '05:30')"""
        if not self._running or self._paused:
            return "已暫停 / 未啟用"
        rem_sec = int(self.get_remaining_seconds())
        days, rem = divmod(rem_sec, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        if days > 0:
            return f"{days}天 {hours:02d}:{minutes:02d}:{seconds:02d}"
        elif hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def get_next_sync_time_str(self) -> str:
        """取得下次預計同步的具體時間字串 (根據目前系統時間與剩餘秒數推算)"""
        if not self._running or self._paused or self._next_sync_mono is None:
            return "無排程"
        rem = self.get_remaining_seconds()
        expected_dt = datetime.now() + timedelta(seconds=rem)
        return expected_dt.strftime("%Y-%m-%d %H:%M:%S")

    def _get_target_servers(self) -> Union[str, List[str]]:
        """取得要查詢的目標伺服器"""
        if self.server_provider:
            try:
                res = self.server_provider()
                if res:
                    return res
            except Exception:
                pass
        return "tock.stdtime.gov.tw"

    def _get_threshold_seconds(self) -> Optional[float]:
        """取得目前設定的誤差閾值"""
        if self.threshold_provider:
            try:
                return self.threshold_provider()
            except Exception:
                pass
        return None

    def _perform_sync(self, ignore_threshold: bool = False):
        """執行時間同步程序並觸發相關回呼"""
        if self._is_syncing:
            return

        with self._lock:
            self._is_syncing = True

        if self.on_sync_start:
            try:
                self.on_sync_start()
            except Exception as e:
                print(f"on_sync_start 回呼發生例外: {e}")

        server = self._get_target_servers()
        threshold = None if ignore_threshold else self._get_threshold_seconds()
        result = self.syncer.sync_time(server, threshold_seconds=threshold)

        with self._lock:
            self._last_sync_time = datetime.now()
            self._last_result = result
            self._is_syncing = False

        if self.on_sync_finish:
            try:
                self.on_sync_finish(result)
            except Exception as e:
                print(f"on_sync_finish 回呼發生例外: {e}")

    def _run_loop(self):
        """背景線程主要迴圈 (基於 time.monotonic)"""
        while not self._stop_event.is_set():
            if not self._paused and self._next_sync_mono is not None:
                now_mono = time.monotonic()
                if now_mono >= self._next_sync_mono:
                    self._perform_sync()
                    with self._lock:
                        self._next_sync_mono = (
                            time.monotonic() + self.interval_seconds
                        )

            # 每秒觸發 on_tick 回呼通知外部更新倒數計時
            rem_sec = self.get_remaining_seconds()
            rem_str = self.get_remaining_formatted()
            if self.on_tick:
                try:
                    self.on_tick(rem_sec, rem_str)
                except Exception:
                    pass

            # 等待 1 秒或直到 stop_event 被觸發
            self._stop_event.wait(1.0)
