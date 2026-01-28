"""Todoist REST API client using only stdlib."""

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

from models import Task, Project, Label


class APIError(Exception):
    """Raised when API request fails."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class TodoistAPI:
    """Client for Todoist REST API v2."""

    BASE_URL = "https://api.todoist.com/rest/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._projects_cache: list[Project] | None = None
        self._labels_cache: list[Label] | None = None

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Make HTTP request to Todoist API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., /tasks)
            data: JSON body data for POST requests
            params: Query parameters for GET requests

        Returns:
            Parsed JSON response or None for 204 responses

        Raises:
            APIError: On HTTP or network errors
        """
        url = f"{self.BASE_URL}{endpoint}"

        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass

            messages = {
                401: "Invalid API token",
                403: "Access denied",
                404: "Resource not found",
                429: "Rate limited, try again later",
            }
            msg = messages.get(e.code, f"API error: {e.code}")
            if error_body:
                try:
                    err_json = json.loads(error_body)
                    if "error" in err_json:
                        msg = err_json["error"]
                except Exception:
                    pass
            raise APIError(msg, e.code)
        except urllib.error.URLError as e:
            raise APIError(f"Network error: {e.reason}")
        except TimeoutError:
            raise APIError("Request timed out")

    def get_projects(self, force_refresh: bool = False) -> list[Project]:
        """Get all projects.

        Args:
            force_refresh: Bypass cache if True

        Returns:
            List of Project objects
        """
        if self._projects_cache is not None and not force_refresh:
            return self._projects_cache

        data = self._request("GET", "/projects")
        projects = [
            Project(
                id=p["id"],
                name=p["name"],
                color=p.get("color", "charcoal"),
                is_inbox=p.get("is_inbox_project", False),
            )
            for p in data
        ]
        self._projects_cache = projects
        return projects

    def get_labels(self, force_refresh: bool = False) -> list[Label]:
        """Get all personal labels.

        Args:
            force_refresh: Bypass cache if True

        Returns:
            List of Label objects
        """
        if self._labels_cache is not None and not force_refresh:
            return self._labels_cache

        data = self._request("GET", "/labels")
        labels = [
            Label(
                id=lbl["id"],
                name=lbl["name"],
                color=lbl.get("color", "charcoal"),
            )
            for lbl in data
        ]
        self._labels_cache = labels
        return labels

    def get_project_name(self, project_id: str) -> str:
        """Look up project name by ID."""
        projects = self.get_projects()
        for p in projects:
            if p.id == project_id:
                return p.name
        return "Unknown"

    def get_tasks(self, filter_str: str | None = None) -> list[Task]:
        """Get active tasks.

        Args:
            filter_str: Todoist filter string (e.g., "today | overdue")

        Returns:
            List of Task objects
        """
        params = {}
        if filter_str:
            params["filter"] = filter_str

        data = self._request("GET", "/tasks", params=params)

        # Pre-fetch projects for name lookups
        projects = self.get_projects()
        project_map = {p.id: p.name for p in projects}

        tasks = []
        for t in data:
            project_name = project_map.get(t["project_id"], "Unknown")
            tasks.append(Task.from_api(t, project_name))

        return tasks

    def create_task(
        self,
        content: str,
        project_id: str | None = None,
        labels: list[str] | None = None,
        priority: int = 1,
        due_string: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            content: Task content/title
            project_id: Optional project ID
            labels: Optional list of label names
            priority: Priority 1-4 (4 is urgent)
            due_string: Human readable due date (e.g., "tomorrow")

        Returns:
            Created Task object
        """
        data: dict[str, Any] = {"content": content}

        if project_id:
            data["project_id"] = project_id
        if labels:
            data["labels"] = labels
        if priority != 1:
            data["priority"] = priority
        if due_string:
            data["due_string"] = due_string

        result = self._request("POST", "/tasks", data=data)
        project_name = self.get_project_name(result["project_id"])
        return Task.from_api(result, project_name)

    def update_task(
        self,
        task_id: str,
        content: str | None = None,
        labels: list[str] | None = None,
        priority: int | None = None,
        due_string: str | None = None,
    ) -> Task:
        """Update an existing task.

        Args:
            task_id: ID of task to update
            content: New content (optional)
            labels: New labels (optional)
            priority: New priority (optional)
            due_string: New due date string (optional)

        Returns:
            Updated Task object
        """
        data: dict[str, Any] = {}

        if content is not None:
            data["content"] = content
        if labels is not None:
            data["labels"] = labels
        if priority is not None:
            data["priority"] = priority
        if due_string is not None:
            data["due_string"] = due_string

        result = self._request("POST", f"/tasks/{task_id}", data=data)
        project_name = self.get_project_name(result["project_id"])
        return Task.from_api(result, project_name)

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as complete.

        Args:
            task_id: ID of task to complete

        Returns:
            True on success
        """
        self._request("POST", f"/tasks/{task_id}/close")
        return True

    def delete_task(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: ID of task to delete

        Returns:
            True on success
        """
        self._request("DELETE", f"/tasks/{task_id}")
        return True

    def clear_cache(self) -> None:
        """Clear cached projects and labels."""
        self._projects_cache = None
        self._labels_cache = None
