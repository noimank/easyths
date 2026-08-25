import io

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def text2df(text: str, sep: str = "\t") -> pd.DataFrame:
    """将客户端复制出的表格文本转换为 DataFrame

    全列按文本读取（dtype=str）：证券代码/合同编号等前导零原样保留，
    数值转换统一由结果模型的字段校验器完成，此处不做类型推断。

    Args:
        text: 输入的文本数据
        sep: 分隔符，默认为制表符\\t

    Returns:
        pandas.DataFrame: 转换后的 DataFrame 对象，如果转换失败则返回空 DataFrame
    """
    try:
        return pd.read_csv(io.StringIO(text), delimiter=sep, dtype=str, na_filter=False)
    except Exception as e:
        logger.error(f"转换文本数据为DataFrame失败: {e}, 输入数据: {text[:100]}")
        return pd.DataFrame()


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 转换为 JSON 可序列化的记录列表（统一的接口交付格式）"""
    if df.empty:
        return []
    return df.to_dict(orient="records")
