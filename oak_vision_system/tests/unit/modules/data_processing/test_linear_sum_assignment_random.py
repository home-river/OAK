import numpy as np
import pytest

# 如果 scipy 不可用或与当前 numpy 不兼容，则跳过测试
try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False
    linear_sum_assignment = None

pytestmark = pytest.mark.skipif(
    not SCIPY_AVAILABLE, reason="scipy 不可用或与当前 numpy 不兼容"
)


def test_linear_sum_assignment_random_matrix():
    """随机代价矩阵应能正常求解最优一对一分配"""
    rng = np.random.RandomState(42)
    cost = rng.rand(5, 4)  # 5 行 4 列

    row_ind, col_ind = linear_sum_assignment(cost)

    # 结果应与行/列数一致（最少取两者较小值）
    assert len(row_ind) == len(col_ind) == min(cost.shape)

    # 行、列索引应唯一（一对一匹配）
    assert len(set(row_ind)) == len(row_ind)
    assert len(set(col_ind)) == len(col_ind)

    # 总成本应等于选中元素之和
    total_cost = cost[row_ind, col_ind].sum()
    assert np.isfinite(total_cost)

