from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list = []
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
