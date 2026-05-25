from pydantic import BaseModel


class ReactionCounters(BaseModel):
    likes: int = 0
    dislikes: int = 0
