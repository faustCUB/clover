from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from datetime import datetime

console = Console()

COLORS = {
    "info":    "#7ec8a0",
    "success": "#00ff88",
    "warn":    "#d4a017",
    "error":   "#ff4f4f",
    "accent":  "#00ff88",
    "dim":     "#3a6b50",
    "time":    "#2d4a38",
}


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(level: str, label: str, message: str) -> None:
    color = COLORS[level]
    time_str = f"[{COLORS['time']}]{_timestamp()}[/]"
    label_str = f"[bold {color}]{label}[/]"
    msg_str = f"[white]{message}[/]"
    console.print(f"{time_str}  {label_str}  {msg_str}")


def info(message: str) -> None:
    _log("info", "INFO   ", message)


def success(message: str) -> None:
    _log("success", "SUCCESS", message)


def warn(message: str) -> None:
    _log("warn", "WARN   ", message)


def error(message: str) -> None:
    _log("error", "ERROR  ", message)


def accent(text: str) -> str:
    return f"[bold {COLORS['accent']}]{text}[/]"


def print_accent(message: str) -> None:
    console.print(message)


def progress(description: str = "Loading...") -> Progress:
    return Progress(
        SpinnerColumn(style=f"bold {COLORS['success']}"),
        TextColumn(f"[{COLORS['info']}]{description}[/]"),
        BarColumn(
            bar_width=30,
            style=COLORS["dim"],
            complete_style=COLORS["success"],
        ),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
