"""Data models for Todoist CLI."""

from dataclasses import dataclass, field


@dataclass
class Project:
    """Represents a Todoist project."""

    id: str
    name: str
    color: str = "charcoal"
    is_inbox: bool = False


@dataclass
class Task:
    """Represents a Todoist task."""

    id: str
    content: str
    project_id: str
    priority: int  # API format: 1 (normal) to 4 (urgent)
    labels: list[str] = field(default_factory=list)
    due_date: str | None = None  # YYYY-MM-DD
    due_time: str | None = None  # HH:MM if datetime present
    due_string: str | None = None  # Human readable due string
    is_completed: bool = False
    description: str = ""
    project_name: str = ""  # Resolved from project_id

    @property
    def priority_label(self) -> str:
        """Get user-facing priority label."""
        return {4: "p1", 3: "p2", 2: "p3", 1: "p4"}.get(self.priority, "p4")

    @classmethod
    def from_api(cls, data: dict, project_name: str = "") -> "Task":
        """Create Task from API v1 response data."""
        due_date = None
        due_time = None
        due_string = None

        if data.get("due"):
            due = data["due"]
            due_string = due.get("string")
            raw_date = due.get("date", "")

            # API v1 folds date+datetime into due.date:
            #   "YYYY-MM-DD" (full-day)
            #   "YYYY-MM-DDTHH:MM:SS" (floating)
            #   "YYYY-MM-DDTHH:MM:SSZ" (UTC)
            if "T" in raw_date:
                due_date = raw_date[:10]  # YYYY-MM-DD portion
                due_time = raw_date[11:16]  # HH:MM portion
            else:
                due_date = raw_date

        # API v1: is_completed derived from completed_at
        is_completed = data.get("completed_at") is not None

        return cls(
            id=data["id"],
            content=data["content"],
            project_id=data["project_id"],
            priority=data.get("priority", 1),
            labels=data.get("labels", []),
            due_date=due_date,
            due_time=due_time,
            due_string=due_string,
            is_completed=is_completed,
            description=data.get("description", ""),
            project_name=project_name,
        )


@dataclass
class Label:
    """Represents a Todoist label."""

    id: str
    name: str
    color: str = "charcoal"
