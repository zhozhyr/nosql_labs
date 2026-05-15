from pydantic import BaseModel


class ReviewCounters(BaseModel):
    count: int = 0
    rating: float = 0.0


class ReviewItem(BaseModel):
    id: str
    event_id: str
    comment: str
    rating: int
    created_at: str
    created_by: str
    updated_at: str
