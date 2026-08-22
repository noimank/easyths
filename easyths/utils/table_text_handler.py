import io

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def text2df(text: str, sep: str = "\t") -> pd.DataFrame:
    """将客户端复制出的表格文本转换为 DataFrame

    Args:
        text: 输入的文本数据
        sep: 分隔符，默认为制表符\\t

    Returns:
        pandas.DataFrame: 转换后的 DataFrame 对象，如果转换失败则返回空 DataFrame
    """
    try:
        return pd.read_csv(io.StringIO(text), delimiter=sep, na_filter=False)
    except Exception as e:
        logger.error(f"转换文本数据为DataFrame失败: {e}, 输入数据: {text[:100]}")
        return pd.DataFrame()


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 转换为 JSON 可序列化的记录列表（统一的接口交付格式）"""
    if df.empty:
        return []
    return df.to_dict(orient="records")
