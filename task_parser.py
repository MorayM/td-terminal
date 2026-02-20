"""Parse user commands and task creation syntax."""

import re
from dataclasses import dataclass
from typing import Any

from models import Project


class TaskParseError(Exception):
    """User-facing error during task string parsing."""


# Priority mapping: user types p1/p2/p3 -> API expects 4/3/2
USER_TO_API_PRIORITY = {"p1": 4, "p2": 3, "p3": 2}

# Due date keywords that Todoist understands
DUE_KEYWORDS = {
    "today",
    "tomorrow",
    "yesterday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "next",
    "week",
    "month",
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
    "january",
    "february",
    "march",
    "april",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


@dataclass
class Command:
    """Parsed user command."""

    type: str  # quit, reload, help, complete, add, edit, delete, filter, unknown
    args: dict[str, Any]


def parse_command(cmd: str) -> Command:
    """Parse a command string into a Command object.

    Args:
        cmd: Raw command string from user

    Returns:
        Command object with type and args
    """
    cmd = cmd.strip()

    if not cmd:
        return Command("empty", {})

    cmd_lower = cmd.lower()

    # Quit commands
    if cmd_lower in ("q", "quit", "exit"):
        return Command("quit", {})

    # Reload
    if cmd_lower in ("r", "reload"):
        return Command("reload", {})

    # Help
    if cmd_lower in ("?", "h", "help"):
        return Command("help", {})

    # Complete task (just a number)
    if cmd.isdigit():
        return Command("complete", {"index": int(cmd)})

    # Edit task (e5, e12, etc.)
    if cmd_lower.startswith("e") and cmd[1:].isdigit():
        return Command("edit", {"index": int(cmd[1:])})

    # Delete task (d5, d12, etc.)
    if cmd_lower.startswith("d") and cmd[1:].isdigit():
        return Command("delete", {"index": int(cmd[1:])})

    # Filter by project (f #Project or f Project)
    if cmd_lower.startswith("f "):
        filter_text = cmd[2:].strip()
        # Remove leading # if present
        if filter_text.startswith("#"):
            filter_text = filter_text[1:]
        return Command("filter", {"project": filter_text})

    # Clear filter
    if cmd_lower == "f":
        return Command("filter", {"project": None})

    # Add task (a or a <task content>)
    if cmd_lower == "a":
        return Command("add", {"prompt": True})
    if cmd_lower.startswith("a "):
        return Command("add", {"prompt": False, "content": cmd[2:].strip()})

    return Command("unknown", {"raw": cmd})


def _check_underscore_ambiguity(projects: list[Project]) -> None:
    """Raise TaskParseError if underscore-to-space normalization is ambiguous.

    Ambiguous when:
    - A project name contains both spaces AND underscores
    - Two projects differ only by spaces vs underscores
    """
    seen_normalized: dict[str, str] = {}
    for p in projects:
        if " " in p.name and "_" in p.name:
            raise TaskParseError(
                f"Project '{p.name}' has both spaces and underscores"
            )
        key = p.name.lower().replace("_", " ")
        if key in seen_normalized and seen_normalized[key] != p.name.lower():
            raise TaskParseError(
                f"Ambiguous projects: '{seen_normalized[key]}' and '{p.name}'"
            )
        seen_normalized[key] = p.name.lower()


def find_project_by_name(name: str, projects: list[Project]) -> Project | None:
    """Find project by name (case-insensitive partial match).

    Underscores in the input are treated as spaces for matching.
    Raises TaskParseError if the underscore convention is ambiguous.

    Args:
        name: Project name to search for (underscores treated as spaces)
        projects: List of available projects

    Returns:
        Matching Project or None
    """
    has_underscore = "_" in name

    if has_underscore:
        _check_underscore_ambiguity(projects)

    name_lower = name.lower()
    normalized = name.lower().replace("_", " ") if has_underscore else name_lower

    # Exact match (original)
    for p in projects:
        if p.name.lower() == name_lower:
            return p

    # Exact match (normalized)
    if has_underscore:
        for p in projects:
            if p.name.lower() == normalized:
                return p

    # Prefix match
    for p in projects:
        if p.name.lower().startswith(name_lower) or (
            has_underscore and p.name.lower().startswith(normalized)
        ):
            return p

    # Contains match
    for p in projects:
        if name_lower in p.name.lower() or (
            has_underscore and normalized in p.name.lower()
        ):
            return p

    return None


def parse_task_string(text: str, projects: list[Project]) -> dict[str, Any]:
    """Parse task creation string into API parameters.

    Syntax: Content text #Project @label p1 tomorrow

    Args:
        text: Raw task string from user
        projects: Available projects for name lookup

    Returns:
        Dict with keys: content, project_id, labels, priority, due_string
    """
    result: dict[str, Any] = {
        "content": "",
        "project_id": None,
        "labels": [],
        "priority": 1,
        "due_string": None,
    }

    working_text = text

    # Extract #project
    project_match = re.search(r"#(\S+)", working_text)
    if project_match:
        project_name = project_match.group(1)
        project = find_project_by_name(project_name, projects)
        if project:
            result["project_id"] = project.id
        working_text = working_text.replace(project_match.group(0), " ")

    # Extract @labels (can be multiple)
    for label_match in re.finditer(r"@(\S+)", working_text):
        result["labels"].append(label_match.group(1))
    working_text = re.sub(r"@\S+", " ", working_text)

    # Extract priority (p1, p2, p3)
    priority_match = re.search(r"\b(p[1-3])\b", working_text, re.IGNORECASE)
    if priority_match:
        result["priority"] = USER_TO_API_PRIORITY[priority_match.group(1).lower()]
        working_text = working_text.replace(priority_match.group(0), " ")

    # Split remaining text into words
    words = working_text.split()

    # Separate content from due date parts
    content_parts = []
    due_parts = []
    in_due_phrase = False

    for i, word in enumerate(words):
        word_lower = word.lower()

        # Check if this word is a due date keyword
        is_due_keyword = word_lower in DUE_KEYWORDS

        # Check if it's a date pattern (YYYY-MM-DD or MM/DD or similar)
        is_date_pattern = bool(re.match(r"^\d{1,4}[-/]\d{1,2}([-/]\d{1,4})?$", word))

        # Check if it's a time pattern (10am, 2:30pm, 14:00)
        is_time_pattern = bool(re.match(r"^\d{1,2}(:\d{2})?(am|pm)?$", word_lower))

        # Check for "at" followed by time
        is_at_time = word_lower == "at" and i + 1 < len(words)

        if is_due_keyword or is_date_pattern or is_time_pattern or in_due_phrase:
            due_parts.append(word)
            in_due_phrase = True
            # Reset if we hit a clear content word
            if (
                not is_due_keyword
                and not is_date_pattern
                and not is_time_pattern
                and not is_at_time
            ):
                if word_lower not in ("at", "on", "by", "in"):
                    in_due_phrase = False
        elif is_at_time:
            due_parts.append(word)
            in_due_phrase = True
        else:
            content_parts.append(word)

    result["content"] = " ".join(content_parts).strip()

    if due_parts:
        result["due_string"] = " ".join(due_parts)

    # If no content extracted, use original text minus special parts
    if not result["content"]:
        result["content"] = text.strip()

    return result


def task_to_edit_string(task) -> str:
    """Convert a task back to editable string format.

    Args:
        task: Task object to convert

    Returns:
        String like "Buy milk #Shopping @home p1 tomorrow"
    """
    parts = [task.content]

    if task.project_name and task.project_name != "Inbox":
        parts.append(f'#{task.project_name.replace(" ", "_")}')

    for label in task.labels:
        parts.append(f"@{label}")

    if task.priority > 1:
        priority_str = {4: "p1", 3: "p2", 2: "p3"}.get(task.priority)
        if priority_str:
            parts.append(priority_str)

    if task.due_string:
        parts.append(task.due_string)
    elif task.due_date:
        parts.append(task.due_date)

    return " ".join(parts)
