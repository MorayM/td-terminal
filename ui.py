"""Curses-based terminal UI for Todoist CLI."""

import curses
from datetime import date

from models import Task, Project

# Color pair IDs
COLOR_P1 = 1  # Red - priority 4 (urgent)
COLOR_P2 = 2  # Yellow - priority 3
COLOR_P3 = 3  # Cyan - priority 2
COLOR_P4 = 4  # White - priority 1 (normal)
COLOR_ERROR = 5  # Red text for errors
COLOR_HEADER = 6  # Header styling
COLOR_DIM = 7  # Dimmed text
COLOR_OVERDUE = 8  # Overdue indicator


def setup_colors():
    """Initialize color pairs for curses."""
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(COLOR_P1, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_P2, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_P3, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_P4, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_ERROR, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_HEADER, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_OVERDUE, curses.COLOR_RED, -1)


def get_priority_color(priority: int) -> int:
    """Get curses color pair for priority level."""
    return {4: COLOR_P1, 3: COLOR_P2, 2: COLOR_P3, 1: COLOR_P4}.get(priority, COLOR_P4)


class TodoistUI:
    """Main UI class for the Todoist terminal client."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.tasks: list[Task] = []
        self.projects: list[Project] = []
        self.scroll_offset = 0
        self.status_message = ""
        self.status_is_error = False
        self.current_filter: str | None = None
        self.input_buffer = ""
        self.cursor_pos = 0
        self._input_scroll = 0
        self.input_mode = "command"  # command, add, edit
        self.edit_task_index: int | None = None

        # Setup
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(100)  # 100ms timeout for getch
        setup_colors()

    def update_tasks(self, tasks: list[Task]):
        """Update the task list."""
        self.tasks = tasks
        self.scroll_offset = 0

    def update_projects(self, projects: list[Project]):
        """Update the projects list."""
        self.projects = projects

    def show_status(self, message: str, is_error: bool = False):
        """Show a status message."""
        self.status_message = message
        self.status_is_error = is_error

    def show_error(self, message: str):
        """Show an error message."""
        self.show_status(message, is_error=True)

    def clear_status(self):
        """Clear the status message."""
        self.status_message = ""
        self.status_is_error = False

    def _get_visible_tasks(self) -> list[Task]:
        """Get tasks filtered by current filter."""
        if not self.current_filter:
            return self.tasks

        filter_lower = self.current_filter.lower()
        return [t for t in self.tasks if filter_lower in t.project_name.lower()]

    def _get_layout(self) -> dict:
        """Calculate layout dimensions."""
        max_y, max_x = self.stdscr.getmaxyx()

        return {
            "max_y": max_y,
            "max_x": max_x,
            "header_y": 0,
            "task_start_y": 2,
            "task_end_y": max_y - 4,
            "input_y": max_y - 3,
            "status_y": max_y - 1,
        }

    def render(self):
        """Render the full UI."""
        self.stdscr.clear()
        layout = self._get_layout()

        self._render_header(layout)
        self._render_tasks(layout)
        self._render_input(layout)
        self._render_status(layout)

        # Position cursor at command prompt (after all rendering)
        self._position_cursor(layout)

        self.stdscr.refresh()

    def render_input_line(self):
        """Redraw only the input row and cursor."""
        layout = self._get_layout()
        y = layout["input_y"]
        try:
            self.stdscr.move(y, 0)
            self.stdscr.clrtoeol()
        except curses.error:
            pass
        self._render_input(layout)
        self._position_cursor(layout)
        self.stdscr.refresh()

    def _render_header(self, layout: dict):
        """Render the header bar."""
        max_x = layout["max_x"]
        visible_tasks = self._get_visible_tasks()

        title = "Todoist Terminal"
        if self.current_filter:
            title += f" - #{self.current_filter}"
        else:
            title += " - Today & Overdue"
        title += f" ({len(visible_tasks)} tasks)"

        # Truncate if too long
        if len(title) > max_x - 2:
            title = title[: max_x - 5] + "..."

        try:
            self.stdscr.addstr(
                layout["header_y"],
                0,
                title.ljust(max_x - 1),
                curses.color_pair(COLOR_HEADER) | curses.A_BOLD,
            )
            self.stdscr.addstr(layout["header_y"] + 1, 0, "─" * (max_x - 1))
        except curses.error:
            pass

    def _render_tasks(self, layout: dict):
        """Render the task list."""
        max_x = layout["max_x"]
        start_y = layout["task_start_y"]
        end_y = layout["task_end_y"]
        visible_height = end_y - start_y

        visible_tasks = self._get_visible_tasks()

        if not visible_tasks:
            try:
                msg = "No tasks! Use 'a' to add one, '?' for help"
                self.stdscr.addstr(start_y + 1, 2, msg, curses.A_DIM)
            except curses.error:
                pass
            return

        # Adjust scroll offset bounds
        max_scroll = max(0, len(visible_tasks) - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        today = date.today().isoformat()

        for i, task in enumerate(
            visible_tasks[self.scroll_offset : self.scroll_offset + visible_height]
        ):
            task_num = self.scroll_offset + i + 1
            y = start_y + i

            if y >= end_y:
                break

            self._render_task_line(y, task_num, task, max_x, today)

        # Scroll indicators
        if self.scroll_offset > 0:
            try:
                self.stdscr.addstr(start_y, max_x - 3, "↑", curses.A_DIM)
            except curses.error:
                pass

        if self.scroll_offset + visible_height < len(visible_tasks):
            try:
                self.stdscr.addstr(end_y - 1, max_x - 3, "↓", curses.A_DIM)
            except curses.error:
                pass

    def _render_task_line(self, y: int, num: int, task: Task, max_x: int, today: str):
        """Render a single task line."""
        # Calculate widths
        num_width = 4
        dot_width = 2
        project_width = min(15, max(8, max_x // 5))
        labels_width = min(15, max(0, max_x // 6))
        time_width = 6
        content_width = (
            max_x
            - num_width
            - dot_width
            - project_width
            - labels_width
            - time_width
            - 4
        )

        try:
            # Task number
            self.stdscr.addstr(y, 0, f"{num:>3}.", curses.A_DIM)

            # Priority dot
            color = get_priority_color(task.priority)
            self.stdscr.addstr(
                y, num_width, "●", curses.color_pair(color) | curses.A_BOLD
            )

            # Content
            content = task.content
            if len(content) > content_width:
                content = content[: content_width - 3] + "..."

            # Check if overdue
            is_overdue = task.due_date and task.due_date < today
            content_attr = curses.color_pair(COLOR_OVERDUE) if is_overdue else 0

            self.stdscr.addstr(
                y, num_width + dot_width, content.ljust(content_width), content_attr
            )

            # Labels (abbreviated)
            x_pos = num_width + dot_width + content_width + 1
            if task.labels and labels_width > 0:
                labels_str = " ".join(f"@{lbl}" for lbl in task.labels[:2])
                if len(labels_str) > labels_width:
                    labels_str = labels_str[: labels_width - 2] + ".."
                self.stdscr.addstr(
                    y, x_pos, labels_str.ljust(labels_width), curses.A_DIM
                )
            x_pos += labels_width

            # Due time
            if task.due_time:
                self.stdscr.addstr(
                    y, x_pos, task.due_time.ljust(time_width), curses.A_DIM
                )
            x_pos += time_width

            # Project name (right-aligned)
            project = task.project_name
            if len(project) > project_width:
                project = project[: project_width - 2] + ".."
            self.stdscr.addstr(
                y, max_x - project_width - 1, project.rjust(project_width), curses.A_DIM
            )

        except curses.error:
            pass

    def _render_input(self, layout: dict):
        """Render the input area."""
        y = layout["input_y"]
        max_x = layout["max_x"]

        try:
            self.stdscr.addstr(y - 1, 0, "─" * (max_x - 1))

            if self.input_mode == "add":
                prompt = "Add task: "
            elif self.input_mode == "edit":
                prompt = "Edit task: "
            else:
                prompt = "> "

            self.stdscr.addstr(y, 0, prompt)

            buffer_x = len(prompt)
            max_buffer = max_x - buffer_x - 2

            if len(self.input_buffer) <= max_buffer:
                self._input_scroll = 0
                display_buffer = self.input_buffer
            else:
                if self.cursor_pos < self._input_scroll:
                    self._input_scroll = self.cursor_pos
                elif self.cursor_pos > self._input_scroll + max_buffer:
                    self._input_scroll = self.cursor_pos - max_buffer
                display_buffer = self.input_buffer[self._input_scroll:self._input_scroll + max_buffer]

            self.stdscr.addstr(y, buffer_x, display_buffer)

        except curses.error:
            pass

    def _position_cursor(self, layout: dict):
        """Position cursor at command prompt input area."""
        y = layout["input_y"]

        if self.input_mode == "add":
            prompt = "Add task: "
        elif self.input_mode == "edit":
            prompt = "Edit task: "
        else:
            prompt = "> "

        buffer_x = len(prompt)
        max_buffer = layout["max_x"] - buffer_x - 2
        scroll = self._input_scroll
        display_cursor = min(self.cursor_pos - scroll, max_buffer)

        try:
            curses.curs_set(1)
            self.stdscr.move(y, buffer_x + display_cursor)
        except curses.error:
            pass

    def _render_status(self, layout: dict):
        """Render the status bar."""
        y = layout["status_y"]
        max_x = layout["max_x"]

        try:
            if self.status_message:
                attr = curses.color_pair(COLOR_ERROR) if self.status_is_error else 0
                msg = self.status_message
                if len(msg) > max_x - 2:
                    msg = msg[: max_x - 5] + "..."
                self.stdscr.addstr(y, 0, msg, attr)
            else:
                hint = "? help | r reload | q quit"
                self.stdscr.addstr(y, 0, hint, curses.A_DIM)
        except curses.error:
            pass

    def handle_scroll(self, direction: int):
        """Handle scroll input."""
        visible_tasks = self._get_visible_tasks()
        layout = self._get_layout()
        visible_height = layout["task_end_y"] - layout["task_start_y"]
        max_scroll = max(0, len(visible_tasks) - visible_height)

        self.scroll_offset = max(0, min(self.scroll_offset + direction, max_scroll))

    def get_input(self) -> tuple[str, str]:
        """Get user input.

        Returns:
            Tuple of (input_type, value) where input_type is:
            - 'command': A complete command was entered
            - 'scroll_up': User pressed up arrow
            - 'scroll_down': User pressed down arrow
            - 'cancel': User pressed Escape
            - 'refresh': Display changed (e.g. typed char, backspace), redraw needed
            - 'none': No input (timeout)
        """
        try:
            ch = self.stdscr.getch()
        except curses.error:
            return ("none", "")

        if ch == -1:
            return ("none", "")

        # Handle special keys
        if ch == curses.KEY_UP:
            return ("scroll_up", "")

        if ch == curses.KEY_DOWN:
            return ("scroll_down", "")

        if ch == curses.KEY_PPAGE:  # Page Up
            return ("page_up", "")

        if ch == curses.KEY_NPAGE:  # Page Down
            return ("page_down", "")

        if ch == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            return ("refresh", "")

        if ch == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
            return ("refresh", "")

        if ch == curses.KEY_HOME:
            self.cursor_pos = 0
            return ("refresh", "")

        if ch == curses.KEY_END:
            self.cursor_pos = len(self.input_buffer)
            return ("refresh", "")

        if ch == 27:  # Escape
            self.input_buffer = ""
            self.cursor_pos = 0
            self.input_mode = "command"
            return ("cancel", "")

        if ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos - 1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
            return ("refresh", "")

        if ch == curses.KEY_ENTER or ch == 10 or ch == 13:
            command = self.input_buffer
            self.input_buffer = ""
            self.cursor_pos = 0
            return ("command", command)

        # Regular character
        if 32 <= ch <= 126:
            c = chr(ch)
            self.input_buffer = self.input_buffer[:self.cursor_pos] + c + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1
            return ("refresh", "")

        return ("none", "")

    def start_add_mode(self):
        """Enter add task mode."""
        self.input_mode = "add"
        self.input_buffer = ""
        self.cursor_pos = 0
        self.clear_status()

    def start_edit_mode(self, task_index: int, initial_text: str):
        """Enter edit task mode."""
        self.input_mode = "edit"
        self.edit_task_index = task_index
        self.input_buffer = initial_text
        self.cursor_pos = len(initial_text)
        self.clear_status()

    def end_input_mode(self):
        """Return to command mode."""
        self.input_mode = "command"
        self.edit_task_index = None
        self.input_buffer = ""
        self.cursor_pos = 0

    def show_help(self):
        """Display help modal."""
        layout = self._get_layout()
        max_y = layout["max_y"]
        max_x = layout["max_x"]

        # Help content
        help_lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "      Todoist Terminal - Help",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Commands:",
            "  NUMBER     Complete task (e.g., 5)",
            "  r          Reload tasks from server",
            "  a          Add new task",
            "  eNUMBER    Edit task (e.g., e5)",
            "  dNUMBER    Delete task (e.g., d5)",
            "  f #Project Filter by project",
            "  f          Clear filter",
            "  ? or h     Show this help",
            "  q          Quit",
            "",
            "Task Creation Syntax:",
            "  Content #Project @label p1 tomorrow",
            "",
            "  #Project   Assign to project",
            "             Use _ for spaces in names",
            "  @label     Add label (multiple ok)",
            "  p1/p2/p3   Set priority (p1=urgent)",
            "",
            "Examples:",
            "  Buy milk #Shopping @home p1 tomorrow",
            "  Review PR @work p2 monday",
            "",
            "Navigation:",
            "  ↑/↓        Scroll task list",
            "  PgUp/PgDn  Scroll by page",
            "  Esc        Cancel current input",
            "",
            "Press any key to close...",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        # Calculate modal dimensions
        modal_width = min(50, max_x - 4)
        modal_height = min(len(help_lines) + 2, max_y - 4)
        start_y = (max_y - modal_height) // 2
        start_x = (max_x - modal_width) // 2

        # Create modal window
        try:
            modal = curses.newwin(modal_height, modal_width, start_y, start_x)
            modal.box()

            for i, line in enumerate(help_lines[: modal_height - 2]):
                if len(line) > modal_width - 4:
                    line = line[: modal_width - 7] + "..."
                try:
                    modal.addstr(i + 1, 2, line)
                except curses.error:
                    pass

            modal.refresh()

            # Wait for any key
            self.stdscr.nodelay(False)
            self.stdscr.getch()
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)

        except curses.error:
            pass

    def confirm_delete(self, task: Task) -> bool:
        """Show delete confirmation dialog.

        Returns:
            True if user confirmed, False otherwise
        """
        layout = self._get_layout()
        max_y = layout["max_y"]
        max_x = layout["max_x"]

        content = task.content
        if len(content) > 30:
            content = content[:27] + "..."

        lines = [
            "Delete task?",
            "",
            f"  {content}",
            "",
            "Press 'y' to confirm, any other key to cancel",
        ]

        modal_width = min(50, max_x - 4)
        modal_height = len(lines) + 4
        start_y = (max_y - modal_height) // 2
        start_x = (max_x - modal_width) // 2

        try:
            modal = curses.newwin(modal_height, modal_width, start_y, start_x)
            modal.box()

            for i, line in enumerate(lines):
                try:
                    modal.addstr(i + 1, 2, line[: modal_width - 4])
                except curses.error:
                    pass

            modal.refresh()

            self.stdscr.nodelay(False)
            ch = self.stdscr.getch()
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)

            return ch in (ord("y"), ord("Y"))

        except curses.error:
            return False
