from abc import ABC, abstractmethod


class BasePrompt(ABC):
    """
    Abstract base for all prompt value objects.

    每個子類別負責持有自己的 template，並透過 render() 將 domain 資料填入
    佔位符後回傳一個新的（filled）prompt 實例。

    使用方式：
        prompt = SomePrompt().render(arg1=..., arg2=...)
        provider.call(prompt.content)

    子類別的 render() 可自訂具名參數，不強制統一簽名，
    因為不同 use case（分析、翻譯、摘要）的 render 輸入截然不同。
    """

    @property
    @abstractmethod
    def content(self) -> str:
        """目前 prompt 的文字內容（可能含未填入的佔位符）。"""
        ...

    @abstractmethod
    def render(self, **kwargs) -> 'BasePrompt':
        """
        填入佔位符後回傳新的 prompt 實例（同型別）。
        子類別應以具名參數覆寫此方法以獲得更好的型別提示：

            def render(self, topic: str, tag_groups: List[TagGroup]) -> 'AnalysisPrompt':
                ...
        """
        ...

    def __str__(self) -> str:
        return self.content
