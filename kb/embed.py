"""嵌入层：文本 -> 向量。

关键设计：**不装 torch**。直接复用本机已有的 llama.cpp 嵌入服务（OpenAI 兼容
/v1/embeddings），零额外模型下载、零 GPU 占用。
"""
import requests

from .config import CFG


class Embedder:
    def __init__(self, base_url=None, model=None, dims=None, batch=16):
        self.base_url = (base_url or CFG["embed_base_url"]).rstrip("/")
        self.model = model or CFG["embed_model"]
        self.dims = dims or CFG["embed_dims"]
        self.batch = batch

    def _post(self, texts):
        r = requests.post(
            f"{self.base_url}/embeddings",
            json={"input": texts, "model": self.model},
            timeout=120,
        )
        if r.status_code != 200:
            raise RuntimeError(f"嵌入服务返回 {r.status_code}: {r.text[:200]}")
        return r.json()["data"]

    def embed(self, texts):
        """返回 [[float,...], ...]"""
        if not texts:
            return []
        out = []
        for i in range(0, len(texts), self.batch):
            part = texts[i:i + self.batch]
            data = self._post(part)
            # 接口按 index 排序，稳妥起见自己排一次
            data = sorted(data, key=lambda d: d.get("index", 0))
            for d in data:
                vec = d["embedding"]
                if len(vec) != self.dims:
                    raise RuntimeError(
                        f"向量维度不符：期望 {self.dims}，实际 {len(vec)}。"
                        f"请检查 config.json 的 embed_dims"
                    )
                out.append(vec)
        return out

    def health(self):
        try:
            r = requests.get(f"{self.base_url}/models", timeout=10)
            return r.status_code == 200
        except Exception:
            return False
