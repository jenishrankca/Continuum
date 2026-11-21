"""Fills the guide's fixed 5-field prompt template from a Shot + the locked StyleBible."""
from __future__ import annotations

from .project import Shot, StyleBible


def build_prompt(shot: Shot, style: StyleBible) -> str:
    """[shot type] of [subject] [action], [camera move], [lighting], [style/grain/grade]"""
    action = shot.subject_action
    if style.genre_mode == "comedy" and shot.beat_before_gag:
        action = f"{action}, {shot.beat_before_gag}"

    field1 = f"{shot.shot_type} of {action}".strip()
    field2 = shot.camera_move
    if shot.camera_angle:
        field2 = f"{shot.camera_angle}, {field2}".strip(", ")
    if shot.lens_composition:
        field2 = f"{field2}, {shot.lens_composition}".strip(", ")
    field3 = style.lighting_phrase
    field4 = f"{style.grain_grade_phrase}, {style.style_phrase}"

    return ", ".join(p for p in [field1, field2, field3, field4] if p)


def effective_image_prompt(shot: Shot, style: StyleBible) -> str:
    """Prefer an explicit image_prompt override; else build the classic 5-field template."""
    if shot.image_prompt.strip():
        return shot.image_prompt.strip()
    return build_prompt(shot, style)


def effective_video_prompt(shot: Shot, style: StyleBible) -> str:
    """Prefer an explicit video_prompt; else derive a light video line from plan fields."""
    if shot.video_prompt.strip():
        return shot.video_prompt.strip()
    base = effective_image_prompt(shot, style)
    extras: list[str] = []
    if shot.duration_s is not None:
        extras.append(f"{shot.duration_s:g}s")
    if shot.camera_move:
        extras.append(shot.camera_move)
    if shot.dialogue_or_sound.strip():
        extras.append(shot.dialogue_or_sound.strip())
    if not extras:
        return base
    return f"{base}; video: {', '.join(extras)}"
