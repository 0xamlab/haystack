"""The one way the fleet writes CSS for its own gr.HTML markup.

`rule()` repeats the class four times so the selector reaches specificity
(0,4,0) and beats Gradio's scoped resets (`.gradio-container-<version> .prose h1`
is (0,3,1)) on every frontend without `!important` or version-coupled selectors —
the discipline the canonical shell established. Nothing here selects Gradio's
own elements.
"""

from __future__ import annotations

REPEAT = 4


def rule(class_name: str, declarations: str, *, suffix: str = "") -> str:
    """`.c.c.c.c<suffix> { declarations }` for one of our classes."""
    if not class_name or " " in class_name or class_name.startswith("."):
        raise ValueError(f"class_name is a bare class name: {class_name!r}")
    body = " ".join(declarations.split())
    if "!important" in body:
        raise ValueError("the fleet never uses !important")
    selector = "".join(f".{class_name}" for _ in range(REPEAT)) + suffix
    return f"{selector} {{ {body} }}"


def block(at_rule: str, *rules: str) -> str:
    """Wrap rules in an at-rule such as `@media (width <= 560px)` or `@supports (...)`."""
    inner = "\n".join(f"  {r}" for r in rules)
    return f"{at_rule} {{\n{inner}\n}}"


def stylesheet(*rules: str) -> str:
    return "\n".join(rules) + "\n"
