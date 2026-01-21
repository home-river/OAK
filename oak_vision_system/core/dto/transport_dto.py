"""
轻量级传输 DTO 基类

用于模块间（尤其是跨线程）传递数据对象：
- 不提供序列化能力
- 不自动生成时间戳等高频开销字段
- 保留统一的验证接口与 frozen 语义下的不可变更新能力
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class TransportDTO(ABC):
    """轻量级传输 DTO 基类。"""

    @abstractmethod
    def _validate_data(self) -> list[str]:
        pass

    def validate(self) -> bool:
        return len(self._validate_data()) == 0

    def get_validation_errors(self) -> list[str]:
        return list(self._validate_data())

    def with_updates(self, **changes: Any) -> "TransportDTO":
        return replace(self, **changes)
