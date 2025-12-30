from queue import Queue, Empty
import threading
from typing import TypeVar

T = TypeVar("T")


class OverflowQueue(Queue[T]):
    """
    支持溢出的泛型队列

    队列满时自动丢弃最旧的元素，保证新元素能够入队。

    特性：
    - 继承自标准 Queue，保留所有原生功能
    - 新增 put_with_overflow() 方法，队列满时自动溢出（丢弃队头最旧元素）
    - 统计累计丢弃次数
    - 背压/压力接口（usage/space/pressure level）
    """

    def __init__(self, maxsize: int = 0):
        """
        初始化溢出队列

        Args:
            maxsize: 队列最大容量，必须 > 0

        Raises:
            ValueError: 如果 maxsize <= 0
        """
        if maxsize <= 0:
            raise ValueError("OverflowQueue 必须指定 maxsize > 0")

        super().__init__(maxsize=maxsize)
        self.drop_count = 0
        self._drop_lock = threading.Lock()

    def put_with_overflow(self, item: T) -> bool:
        """
        放入元素，队列满时丢弃最旧的元素。

        该方法永不阻塞：队列满时自动丢弃队头元素以腾出空间。

        Args:
            item: 要放入的元素

        Returns:
            bool: 是否丢弃了旧元素
                - True: 队列已满，丢弃了一个旧元素
                - False: 队列未满，正常放入

        注意：
            该方法会“丢弃旧元素”来保证新元素写入，因此业务上必须能接受丢帧/丢包。
        """
        with self.mutex:
            dropped = False

            if self._qsize() >= self.maxsize:
                # 队列满：丢弃最旧元素
                self._get()

                # 关键：被丢弃的元素永远不会有 task_done()，因此要修正 unfinished_tasks
                # 做防御性下限保护，避免异常用法导致负数
                if self.unfinished_tasks > 0:
                    self.unfinished_tasks -= 1
                else:
                    self.unfinished_tasks = 0

                # 如果因此变为 0，需要唤醒 join() 的等待者
                if self.unfinished_tasks == 0:
                    self.all_tasks_done.notify_all()

                with self._drop_lock:
                    self.drop_count += 1

                dropped = True

            # 放入新元素（不走 put()，因此要手动维护计数/通知）
            self._put(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

            return dropped

    # ========== 统计接口 ==========

    def get_drop_count(self) -> int:
        """
        获取累计丢弃次数

        Returns:
            int: 自队列创建以来累计丢弃的元素数量（统计的是“被挤掉的旧元素”次数）
        """
        with self._drop_lock:
            return self.drop_count

    def reset_drop_count(self) -> None:
        """
        重置丢弃计数器

        用于统计周期性的丢弃情况。
        """
        with self._drop_lock:
            self.drop_count = 0

    # ========== 背压控制接口 ==========

    def get_usage_ratio(self) -> float:
        """
        获取队列使用率

        Returns:
            float: 队列使用率，范围 [0.0, 1.0]
        """
        with self.mutex:
            # maxsize > 0 在 __init__ 已保证
            return self._qsize() / self.maxsize

    def get_available_space(self) -> int:
        """
        获取队列剩余空间

        Returns:
            int: 队列中还能放入多少元素
        """
        with self.mutex:
            return self.maxsize - self._qsize()

    def is_under_pressure(self, threshold: float = 0.8) -> bool:
        """
        检查队列是否处于压力状态

        当队列使用率超过阈值时认为处于压力状态。

        Args:
            threshold: 使用率阈值，范围 [0.0, 1.0]，默认 0.8

        Returns:
            bool: 是否处于压力状态
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold 必须在 [0.0, 1.0] 范围内，当前值: {threshold}")

        return self.get_usage_ratio() >= threshold

    def is_nearly_full(self, threshold: int = 1) -> bool:
        """
        检查队列是否接近满载（按“剩余空位”判断）

        Args:
            threshold: 剩余空间阈值，默认 1（仅剩 1 个空位）

        Returns:
            bool: 是否接近满载
        """
        if threshold < 0:
            raise ValueError(f"threshold 必须 >= 0，当前值: {threshold}")

        return self.get_available_space() <= threshold

    def get_pressure_level(self) -> str:
        """
        获取队列压力等级

        Returns:
            str: "low" | "medium" | "high" | "critical"
        """
        usage = self.get_usage_ratio()

        if usage < 0.5:
            return "low"
        elif usage < 0.8:
            return "medium"
        elif usage < 0.95:
            return "high"
        else:
            return "critical"

    # ========== 类型安全的重载 ==========

    def get(self, block: bool = True, timeout: float | None = None) -> T:
        """
        获取元素（类型安全的重载）
        """
        return super().get(block=block, timeout=timeout)

    def get_nowait(self) -> T:
        """
        非阻塞获取元素（类型安全的重载）
        """
        return super().get_nowait()
