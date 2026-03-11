def format_cooldown(seconds_remaining: float) -> str:
    """Return a `Xm Ys` countdown string from remaining seconds."""
    total = int(seconds_remaining)
    mins = total // 60
    secs = total % 60
    return f"{mins}m {secs}s"


def multiline_text(lines: list[str]) -> str:
    """Join lines with newlines for embed description blocks."""
    return "\n".join(lines)
