from pydantic import BaseModel, Field
from typing import List, Optional


class DayWindow(BaseModel):
    """Start/end times for one specific day."""
    start: str
    end: str


class TripRequest(BaseModel):
    user_id: str
    destination_city: str
    start_date: str
    end_date: str
    transport_mode: str
    selected_keywords: List[str] = []
    daily_start_time: str = "09:00"
    daily_end_time: str = "18:00"
    # Optional per-day overrides; missing days fall back to the two fields above.
    daily_windows: List[DayWindow] = []


class ReorderRequest(BaseModel):
    day_number: int
    ordered_stop_ids: List[str]


class DurationRequest(BaseModel):
    """New total visit length for a single stop, in minutes."""
    duration_minutes: int = Field(..., ge=15, le=600)


class PreviewRequest(BaseModel):
    """Ask what an edit would do, without doing it."""
    action: str  # delete | replace | extend | move
    target_day: Optional[int] = None
    duration_minutes: Optional[int] = Field(default=None, ge=15, le=600)


class ReplaceRequest(BaseModel):
    """Optional: reuse the candidate a preview already proposed."""
    place_id: Optional[str] = None


class AddStopRequest(BaseModel):
    """A place the traveller accepted from the day's suggestions."""
    place_id: str
