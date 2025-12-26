import pandas as pd
import io
import structlog
logger = structlog.get_logger(__name__)

#预留的未来可能需要
def pre_process_text(text, pre_process_type=None):
    if pre_process_type is None:
        return text




def text2df(text, pre_process_type=None, sep="\t"):
    """
    将文本数据转换为DataFrame格式

    Args:
        text (str): 输入的文本数据
        pre_process_type (str, optional): 预处理类型，默认为None
        sep (str, optional): 分隔符，默认为制表符\t

    Returns:
        pandas.DataFrame: 转换后的DataFrame对象，如果转换失败则返回空DataFrame
    """
    data = pre_process_text(text, pre_process_type)
    try:
        df = pd.read_csv(
            io.StringIO(data),
            delimiter=sep,
            na_filter=False,
        )
        return df
    except Exception as e:
        logger.error(f"转换文本数据为DataFrame失败: {e}, 输入数据: {text[:100]}")
        return pd.DataFrame()


def df_format_convert(df, format_type):
    """
    将DataFrame格式转换为指定格式
    """
    if format_type == "markdown":
        return df.to_markdown()
    elif format_type == "json" or format_type == "dict":
        return df.to_dict(orient="records")
    elif format_type == "str":
        return df.to_string(index=False)
    else:
        return df







