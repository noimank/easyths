"""市价委托成交策略：对外契约定义 + 客户端下拉框内容匹配工具。

``EXECUTION_STRATEGIES`` 是接口对外的编号契约（整数编号 → 标准名称），
调用方通过编号指定成交策略。但客户端（同花顺）下单界面中市价成交策略的
**数量和顺序都是不定的**，且同一策略在界面上的中文名称可能有多种写法
（如「对手方最优」/「对手方最优价格申报」）。因此定位下拉框选项时必须按
名称内容匹配，绝不能按编号或位置定位。
"""

# 对外契约：成交策略编号 → 标准名称（仅用于接口文档、日志与返回信息，不参与下拉框定位）
EXECUTION_STRATEGIES: dict[int, str] = {
    1: "对手方最优",
    2: "本方最优",
    3: "五档即成剩撤",
    4: "即成剩撤",
    5: "全额成交或撤",
    6: "五档即成剩转限",
}

# 兜底策略编号：请求策略不被标的支持（或编号不合法）时使用
DEFAULT_STRATEGY: int = 3

# 各策略在客户端下拉框中可能出现的中文名称变体。
# 只要关键词是被匹配文本的子串即命中，因此每个策略只需给出最能区分的词，
# 如「对手方最优」可同时命中「对手方最优」与「对手方最优价格申报」。
# 注意 3/6 号保留两种前缀写法：官方全称带「最优」（最优五档即时成交剩余...），
# 部分券商省略「最优」（五档即时成交剩余...）。
_STRATEGY_KEYWORDS: dict[int, list[str]] = {
    1: ["对手方最优"],
    2: ["本方最优"],
    6: ["最优五档即时成交剩余转限价", "五档即时成交剩余转限价", "五档即成剩转限"],
    3: ["最优五档即时成交剩余撤销", "五档即时成交剩余撤销", "五档即成剩撤"],
    4: ["即时成交剩余撤销", "即成剩撤"],
    5: ["全额成交或撤", "全额或撤", "全部成交或撤"],
}

# 按优先级扁平化：靠前的关键词更具体。3 号（最优五档）的关键词是 4 号
# （即时成交）关键词的超集，必须先于 4 号判断，否则「最优五档即时成交
# 剩余撤销申报」会被误判为 4 号策略。
_ORDERED_KEYWORDS: list[tuple[int, str]] = [
    (strategy, keyword)
    for strategy in (1, 2, 6, 3, 4, 5)
    for keyword in _STRATEGY_KEYWORDS[strategy]
]


def resolve_strategy(
    combo_texts: list[str], requested_strategy: int
) -> tuple[int, str, int] | None:
    """在客户端下拉框文本中定位应选择的策略项。

    Args:
        combo_texts: 下拉框各项文本列表，顺序与各项索引一致。
        requested_strategy: 接口请求的策略编号；不在契约范围内时按兜底策略处理。

    Returns:
        ``(选中的策略编号, 匹配到的下拉框文本, 下拉框项索引)``；
        若请求策略与兜底策略都不被该标的支持，返回 ``None``。
    """
    requested_strategy = (
        requested_strategy
        if requested_strategy in _STRATEGY_KEYWORDS
        else DEFAULT_STRATEGY
    )

    # 先把每个下拉框项按关键词归属到具体策略，避免模糊子串互相污染
    item_strategy: dict[int, int] = {}
    for index, text in enumerate(combo_texts):
        for strategy, keyword in _ORDERED_KEYWORDS:
            if keyword in text:
                item_strategy[index] = strategy
                break

    # 请求策略优先，其次兜底策略
    for strategy in (requested_strategy, DEFAULT_STRATEGY):
        for index, matched_strategy in item_strategy.items():
            if matched_strategy == strategy:
                return strategy, combo_texts[index], index
    return None
