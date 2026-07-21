from __future__ import annotations


class TUnderstandError(Exception):
    """Base error with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}
