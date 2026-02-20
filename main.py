#!/usr/bin/env python3
"""Todoist CLI - Interactive terminal client for Todoist."""

import curses
import sys
from config import load_config, ConfigError
from todoist_api import TodoistAPI, APIError
from models import Task
from task_parser import parse_command, parse_task_string, task_to_edit_string
from ui import TodoistUI


def sort_tasks(tasks: list[Task]) -> list[Task]:
    """Sort tasks by: priority first, then due date/time (soonest first).

    Args:
        tasks: List of tasks to sort

    Returns:
        Sorted list of tasks
    """

    def sort_key(task: Task):
        # Primary: priority (API: 4=urgent, 1=normal; negate so urgent first)
        priority_sort = -task.priority

        # Secondary: due date (earlier first, None last)
        due_sort = task.due_date if task.due_date else "9999-99-99"

        # Tertiary: due time (earlier first, None last)
        time_sort = task.due_time if task.due_time else "99:99"

        return (priority_sort, due_sort, time_sort)

    return sorted(tasks, key=sort_key)


def reload_tasks(api: TodoistAPI) -> list[Task]:
    """Fetch and sort tasks from API.

    Args:
        api: TodoistAPI instance

    Returns:
        Sorted list of tasks
    """
    tasks = api.get_tasks(filter_str="(today | overdue)")
    return sort_tasks(tasks)


def handle_command(
    cmd_str: str,
    ui: TodoistUI,
    api: TodoistAPI,
    tasks: list[Task],
) -> tuple[str, list[Task]]:
    """Process a command and return result.

    Args:
        cmd_str: Raw command string
        ui: UI instance
        api: API client
        tasks: Current task list

    Returns:
        Tuple of (action, updated_tasks) where action is:
        - 'quit': Exit the application
        - 'continue': Keep running
    """
    cmd = parse_command(cmd_str)

    if cmd.type == "empty":
        return ("continue", tasks)

    if cmd.type == "quit":
        return ("quit", tasks)

    if cmd.type == "reload":
        try:
            ui.show_status("Reloading...")
            ui.render()
            tasks = reload_tasks(api)
            ui.update_tasks(tasks)
            ui.show_status(f"Loaded {len(tasks)} tasks")
        except APIError as e:
            ui.show_error(str(e))
        return ("continue", tasks)

    if cmd.type == "help":
        ui.show_help()
        return ("continue", tasks)

    if cmd.type == "complete":
        idx = cmd.args["index"] - 1
        visible = ui._get_visible_tasks()
        if 0 <= idx < len(visible):
            task = visible[idx]
            try:
                ui.show_status(f"Completing '{task.content[:30]}...'")
                ui.render()
                api.complete_task(task.id)
                tasks = reload_tasks(api)
                ui.update_tasks(tasks)
                ui.show_status("Task completed!")
            except APIError as e:
                ui.show_error(str(e))
        else:
            ui.show_error(f"Invalid task number: {cmd.args['index']}")
        return ("continue", tasks)

    if cmd.type == "delete":
        idx = cmd.args["index"] - 1
        visible = ui._get_visible_tasks()
        if 0 <= idx < len(visible):
            task = visible[idx]
            if ui.confirm_delete(task):
                try:
                    ui.show_status("Deleting...")
                    ui.render()
                    api.delete_task(task.id)
                    tasks = reload_tasks(api)
                    ui.update_tasks(tasks)
                    ui.show_status("Task deleted")
                except APIError as e:
                    ui.show_error(str(e))
            else:
                ui.show_status("Delete cancelled")
        else:
            ui.show_error(f"Invalid task number: {cmd.args['index']}")
        return ("continue", tasks)

    if cmd.type == "filter":
        project = cmd.args.get("project")
        if project:
            ui.current_filter = project
            ui.show_status(f"Filtering by: {project}")
        else:
            ui.current_filter = None
            ui.show_status("Filter cleared")
        ui.scroll_offset = 0
        return ("continue", tasks)

    if cmd.type == "add":
        if cmd.args.get("prompt"):
            ui.start_add_mode()
        else:
            # Direct add with content
            content = cmd.args.get("content", "")
            if content:
                return handle_add_task(content, ui, api, tasks)
        return ("continue", tasks)

    if cmd.type == "edit":
        idx = cmd.args["index"] - 1
        visible = ui._get_visible_tasks()
        if 0 <= idx < len(visible):
            task = visible[idx]
            edit_str = task_to_edit_string(task)
            ui.start_edit_mode(idx, edit_str)
        else:
            ui.show_error(f"Invalid task number: {cmd.args['index']}")
        return ("continue", tasks)

    if cmd.type == "unknown":
        ui.show_error(f"Unknown command: {cmd.args.get('raw', '')}")
        return ("continue", tasks)

    return ("continue", tasks)


def handle_add_task(
    content: str,
    ui: TodoistUI,
    api: TodoistAPI,
    tasks: list[Task],
) -> tuple[str, list[Task]]:
    """Handle adding a new task.

    Args:
        content: Task string to parse
        ui: UI instance
        api: API client
        tasks: Current task list

    Returns:
        Tuple of (action, updated_tasks)
    """
    if not content.strip():
        ui.show_error("Task content cannot be empty")
        return ("continue", tasks)

    try:
        parsed = parse_task_string(content, ui.projects)

        ui.show_status("Creating task...")
        ui.render()

        api.create_task(
            content=parsed["content"],
            project_id=parsed["project_id"],
            labels=parsed["labels"],
            priority=parsed["priority"],
            due_string=parsed["due_string"] or "today",
        )

        tasks = reload_tasks(api)
        ui.update_tasks(tasks)
        ui.show_status("Task created!")

    except APIError as e:
        ui.show_error(str(e))

    return ("continue", tasks)


def handle_edit_task(
    task_index: int,
    content: str,
    ui: TodoistUI,
    api: TodoistAPI,
    tasks: list[Task],
) -> tuple[str, list[Task]]:
    """Handle editing an existing task.

    Args:
        task_index: Index of task in visible list
        content: New task string to parse
        ui: UI instance
        api: API client
        tasks: Current task list

    Returns:
        Tuple of (action, updated_tasks)
    """
    visible = ui._get_visible_tasks()
    if not (0 <= task_index < len(visible)):
        ui.show_error("Invalid task")
        return ("continue", tasks)

    task = visible[task_index]

    if not content.strip():
        ui.show_error("Task content cannot be empty")
        return ("continue", tasks)

    try:
        parsed = parse_task_string(content, ui.projects)

        ui.show_status("Updating task...")
        ui.render()

        api.update_task(
            task_id=task.id,
            content=parsed["content"],
            labels=parsed["labels"],
            priority=parsed["priority"],
            due_string=parsed["due_string"],
        )

        tasks = reload_tasks(api)
        ui.update_tasks(tasks)
        ui.show_status("Task updated!")

    except APIError as e:
        ui.show_error(str(e))

    return ("continue", tasks)


def main_loop(stdscr, api: TodoistAPI, tasks: list[Task], projects):
    """Main UI event loop.

    Args:
        stdscr: Curses screen object
        api: TodoistAPI instance
        tasks: Initial task list
        projects: List of projects
    """
    ui = TodoistUI(stdscr)
    ui.update_tasks(tasks)
    ui.update_projects(projects)
    ui.show_status(f"Loaded {len(tasks)} tasks")
    ui.render()

    while True:
        input_type, value = ui.get_input()

        if input_type == "none":
            continue

        if input_type == "refresh":
            ui.render_input_line()
            continue

        if input_type == "cancel":
            ui.end_input_mode()
            ui.clear_status()
            ui.render()
            continue

        if input_type == "scroll_up":
            ui.handle_scroll(-1)
            ui.render()
            continue

        if input_type == "scroll_down":
            ui.handle_scroll(1)
            ui.render()
            continue

        if input_type == "page_up":
            ui.handle_scroll(-10)
            ui.render()
            continue

        if input_type == "page_down":
            ui.handle_scroll(10)
            ui.render()
            continue

        if input_type == "command":
            # Handle based on current mode
            if ui.input_mode == "add":
                action, tasks = handle_add_task(value, ui, api, tasks)
                ui.end_input_mode()
            elif ui.input_mode == "edit":
                action, tasks = handle_edit_task(
                    ui.edit_task_index, value, ui, api, tasks
                )
                ui.end_input_mode()
            else:
                action, tasks = handle_command(value, ui, api, tasks)

            if action == "quit":
                break
            ui.render()


def main():
    """Application entry point."""
    # Load configuration
    try:
        config = load_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Create a .env file with TODOIST_API_KEY=your_token", file=sys.stderr)
        sys.exit(1)

    # Initialize API client
    api = TodoistAPI(config["api_key"])

    # Initial data load
    print("Loading tasks from Todoist...")
    try:
        projects = api.get_projects()
        api.get_labels()  # Pre-cache labels
        tasks = reload_tasks(api)
    except APIError as e:
        print(f"Failed to load data: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(tasks)} tasks. Starting UI...")

    # Set terminal window title
    print("\033]0;Todoist Terminal\007", end="", flush=True)

    # Run the curses UI
    try:
        curses.wrapper(main_loop, api, tasks, projects)
    except KeyboardInterrupt:
        pass

    # Reset terminal title
    print("\033]0;\007", end="", flush=True)
    print("Goodbye!")


if __name__ == "__main__":
    main()
