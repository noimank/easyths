"""市价成交策略匹配逻辑的单元测试（无需连接同花顺客户端）。"""

from easyths.utils.execution_strategy import (
    DEFAULT_STRATEGY,
    EXECUTION_STRATEGIES,
    resolve_strategy,
)

# 上证/深证常见市价委托下拉框（全称写法，顺序不定）
FULL_NAMES = [
    "对手方最优价格申报",
    "本方最优价格申报",
    "即时成交剩余撤销申报",
    "最优五档即时成交剩余撤销申报",
    "全额成交或撤销申报",
]

# 部分客户端使用简称写法
ABBREV_NAMES = [
    "对手方最优",
    "本方最优",
    "五档即成剩撤",
    "即成剩撤",
    "全额成交或撤",
]


def test_match_full_names():
    """全称下拉框按名称内容定位，不受顺序影响。"""
    assert resolve_strategy(FULL_NAMES, 1) == (1, "对手方最优价格申报", 0)
    assert resolve_strategy(FULL_NAMES, 2) == (2, "本方最优价格申报", 1)
    assert resolve_strategy(FULL_NAMES, 3) == (3, "最优五档即时成交剩余撤销申报", 3)
    assert resolve_strategy(FULL_NAMES, 4) == (4, "即时成交剩余撤销申报", 2)
    assert resolve_strategy(FULL_NAMES, 5) == (5, "全额成交或撤销申报", 4)


def test_match_abbreviated_names():
    """简称写法下拉框同样按内容匹配。"""
    assert resolve_strategy(ABBREV_NAMES, 1) == (1, "对手方最优", 0)
    assert resolve_strategy(ABBREV_NAMES, 3) == (3, "五档即成剩撤", 2)
    assert resolve_strategy(ABBREV_NAMES, 4) == (4, "即成剩撤", 3)


def test_five_level_remaining_convert_to_limit():
    """上交所特有策略「最优五档即时成交剩余转限价」可正确识别。"""
    texts = [
        "最优五档即时成交剩余转限价申报",
        "对手方最优价格申报",
        "本方最优价格申报",
        "即时成交剩余撤销申报",
        "最优五档即时成交剩余撤销申报",
        "全额成交或撤销申报",
    ]
    assert resolve_strategy(texts, 6) == (6, "最优五档即时成交剩余转限价申报", 0)


def test_fuzzy_substring_not_misjudged():
    """「最优五档即时成交剩余撤销」不得被误判为策略4（即成剩撤）。

    策略4 的关键词「即时成交剩余撤销」是策略3 全称的子串，请求 4 时必须
    定位到真正的「即时成交剩余撤销申报」而非「最优五档...」。
    """
    assert resolve_strategy(FULL_NAMES, 4) == (4, "即时成交剩余撤销申报", 2)


def test_out_of_range_requested_falls_back_to_default():
    """超出契约范围的编号视为不合法，直接使用兜底策略。"""
    assert resolve_strategy(FULL_NAMES, 7) == (
        DEFAULT_STRATEGY,
        "最优五档即时成交剩余撤销申报",
        3,
    )


def test_unsupported_requested_falls_back_to_default():
    """标的支持兜底策略但不支持请求策略时，回退到兜底策略。"""
    # 无「即时成交剩余撤销」，即不支持策略4
    texts = [
        "对手方最优价格申报",
        "本方最优价格申报",
        "最优五档即时成交剩余撤销申报",
        "全额成交或撤销申报",
    ]
    assert resolve_strategy(texts, 4) == (
        DEFAULT_STRATEGY,
        "最优五档即时成交剩余撤销申报",
        2,
    )


def test_neither_requested_nor_default_supported_returns_none():
    """请求策略与兜底策略均不被标的支持时返回 None。"""
    texts = ["对手方最优价格申报", "本方最优价格申报", "全额成交或撤销申报"]
    assert resolve_strategy(texts, DEFAULT_STRATEGY) is None


def test_no_optimal_prefix_variants():
    """券商省略「最优」前缀的写法（五档即时成交剩余撤销/转限价）也能识别。

    且「五档即时成交剩余撤销」不得被误判为策略4（即成剩撤）。
    """
    texts = [
        "对手方最优价格申报",
        "本方最优价格申报",
        "五档即时成交剩余撤销申报",  # 策略3（无「最优」前缀）
        "即时成交剩余撤销申报",  # 策略4
        "五档即时成交剩余转限价申报",  # 策略6（无「最优」前缀）
        "全额成交或撤销申报",
    ]
    assert resolve_strategy(texts, 3) == (3, "五档即时成交剩余撤销申报", 2)
    assert resolve_strategy(texts, 4) == (4, "即时成交剩余撤销申报", 3)
    assert resolve_strategy(texts, 6) == (6, "五档即时成交剩余转限价申报", 4)


def test_strategy5_short_and_alternate_wording():
    """策略5 的短写法「全额或撤」与「全部」替换「全额」的写法。"""
    assert resolve_strategy(["对手方最优", "全额或撤"], 5) == (5, "全额或撤", 1)
    assert resolve_strategy(["对手方最优", "全部成交或撤销申报"], 5) == (
        5,
        "全部成交或撤销申报",
        1,
    )


def test_contract_covers_all_external_strategies():
    """对外契约中的每个编号都有对应的下拉框关键词，且兜底策略编号合法。"""
    from easyths.utils.execution_strategy import _STRATEGY_KEYWORDS

    assert set(EXECUTION_STRATEGIES) == set(_STRATEGY_KEYWORDS)
    assert DEFAULT_STRATEGY in EXECUTION_STRATEGIES
    assert all(EXECUTION_STRATEGIES[n] for n in EXECUTION_STRATEGIES)
