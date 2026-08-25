"""表格文本处理单元测试：全列按文本读取，前导零代码类字段不被数值化。"""

from easyths.operations.holding_query import HoldingQueryOperation
from easyths.operations.order_query import OrderQueryOperation
from easyths.utils import df_to_records, text2df

HOLDING_CLIPBOARD = (
    "证券代码\t证券名称\t持仓数量\t可用数量\t冻结数量\t参考成本价\t当前价\t浮动盈亏\t"
    "盈亏比例(%)\t当日盈亏\t当日盈亏比(%)\t最新市值\t仓位占比(%)\t当日买入\t当日卖出\t"
    "交易市场\t操作\n"
    "000001\t平安银行\t1,200\t1,200\t0\t10.50\t10.65\t180.00\t1.76\t--\t--\t"
    "12,780.00\t12.30\t0\t0\t深圳\t买入 卖出\n"
    "002415\t海康威视\t300\t300\t0\t28.80\t29.10\t90.00\t1.04\t--\t--\t"
    "8,730.00\t8.42\t0\t0\t深圳\t买入 卖出"
)

ORDER_CLIPBOARD = (
    "委托时间\t证券代码\t证券名称\t操作\t备注\t委托数量\t成交数量\t委托价格\t成交均价\t"
    "撤销数量\t合同编号\t交易市场\n"
    "09:30:00\t000001\t平安银行\t买入\t\t100\t0\t10.50\t--\t0\t000123\t深圳"
)


def test_text2df_reads_all_columns_as_text():
    df = text2df(HOLDING_CLIPBOARD)
    assert all(isinstance(v, str) for v in df.to_numpy().ravel())
    assert df["证券代码"].tolist() == ["000001", "002415"]
    # 数值列同样保持客户端原样文本，转换交给行模型
    assert df["冻结数量"].tolist() == ["0", "0"]


def test_holding_pipeline_preserves_leading_zero_code():
    """剪贴板 → DataFrame → 持仓行模型：前导零保留，数值字段照常转换。"""
    records = df_to_records(text2df(HOLDING_CLIPBOARD))
    rows = [HoldingQueryOperation().parse_holding_row(r).model_dump() for r in records]
    assert [row["stock_code"] for row in rows] == ["000001", "002415"]
    assert rows[0]["quantity"] == 1200
    assert rows[0]["current_price"] == 10.65
    assert rows[0]["daily_profit"] is None


def test_order_pipeline_preserves_leading_zero_contract_no():
    """委托行的证券代码/合同编号前导零原样保留。"""
    record = df_to_records(text2df(ORDER_CLIPBOARD))[0]
    row = OrderQueryOperation().parse_order_row(record).model_dump()
    assert row["stock_code"] == "000001"
    assert row["contract_no"] == "000123"
    assert row["price"] == 10.5
