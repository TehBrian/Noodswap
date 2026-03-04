def format_cooldown(seconds_remaining: float) -> str:
    total = int(seconds_remaining)
    mins = total // 60
    secs = total % 60
    return f"{mins}m {secs}s"


def multiline_text(lines: list[str]) -> str:
    if not lines:
        return ""

    text = lines[0]
    for line in lines[1:]:
        text = f"""{text}
{line}"""
    return text
