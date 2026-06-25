class WpsEnhancerError(Exception):
    """项目所有自定义异常的基类。"""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class FileReadError(WpsEnhancerError):
    """文件无法读取（格式损坏/权限不足/不支持的格式）。"""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ColumnNotFoundError(WpsEnhancerError):
    """配置的列名在 Sheet headers 中不存在。"""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class DataProcessError(WpsEnhancerError):
    """数据处理过程中的意外异常。"""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class FileWriteError(WpsEnhancerError):
    """输出文件写入失败（路径无权限/磁盘空间不足）。"""
    def __init__(self, message: str) -> None:
        super().__init__(message)
