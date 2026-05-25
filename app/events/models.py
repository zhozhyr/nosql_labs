from pydantic import BaseModel, ConfigDict


class CreateEventRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    address: str
    started_at: str
    finished_at: str
    description: str


class EventItem(BaseModel):
    id: str
    title: str
    description: str
    location: dict[str, str]
    created_at: str
    created_by: str
    started_at: str
    finished_at: str


class ListEventsResponse(BaseModel):
    events: list[EventItem]
    count: int
