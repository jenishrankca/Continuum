"""Stage 7 storyboard / shot planning helpers (vision §7)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import prompt_builder
from .project import Project, Shot


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_shot(project: Project, shot_id: str) -> Shot:
    shot = project.get_shot(shot_id)
    if shot is None:
        raise KeyError(f"Unknown shot id '{shot_id}'")
    return shot


def link_sequence(project: Project, *, overwrite: bool = False) -> int:
    """Set prev_shot_id / next_shot_id from shot order. Returns shots updated."""
    ordered = sorted(project.shots, key=lambda s: s.order)
    updated = 0
    for i, shot in enumerate(ordered):
        new_prev = ordered[i - 1].id if i > 0 else None
        new_next = ordered[i + 1].id if i + 1 < len(ordered) else None
        if overwrite or (shot.prev_shot_id is None and shot.next_shot_id is None):
            if shot.prev_shot_id != new_prev or shot.next_shot_id != new_next:
                shot.prev_shot_id = new_prev
                shot.next_shot_id = new_next
                updated += 1
            elif overwrite:
                # already correct; still count as linked when overwrite requested
                pass
        elif overwrite:
            shot.prev_shot_id = new_prev
            shot.next_shot_id = new_next
            updated += 1
    return updated


def sync_prompts(project: Project, *, overwrite: bool = False) -> dict[str, int]:
    """Fill empty image_prompt / video_prompt from builders. Returns counts filled."""
    style = project.style
    image_n = 0
    video_n = 0
    for shot in project.shots:
        built_img = prompt_builder.build_prompt(shot, style)
        if overwrite or not shot.image_prompt.strip():
            if shot.image_prompt != built_img:
                shot.image_prompt = built_img
                image_n += 1
        # Derive video with stored override temporarily cleared
        saved_vid = shot.video_prompt
        shot.video_prompt = ""
        derived_vid = prompt_builder.effective_video_prompt(shot, style)
        if overwrite or not saved_vid.strip():
            if saved_vid != derived_vid:
                shot.video_prompt = derived_vid
                video_n += 1
            else:
                shot.video_prompt = saved_vid
        else:
            shot.video_prompt = saved_vid
    return {"image_prompt": image_n, "video_prompt": video_n}


def update_shot(
    project: Project,
    shot_id: str,
    *,
    description: Optional[str] = None,
    label: Optional[str] = None,
    shot_type: Optional[str] = None,
    camera_angle: Optional[str] = None,
    camera_move: Optional[str] = None,
    lens_composition: Optional[str] = None,
    subject_action: Optional[str] = None,
    dialogue_or_sound: Optional[str] = None,
    duration_s: Optional[float] = None,
    clear_duration: bool = False,
    prev_shot_id: Optional[str] = None,
    next_shot_id: Optional[str] = None,
    clear_prev: bool = False,
    clear_next: bool = False,
    continuity_state_id: Optional[str] = None,
    clear_continuity_state: bool = False,
    start_keyframe_path: Optional[str] = None,
    end_keyframe_path: Optional[str] = None,
    clear_start_keyframe: bool = False,
    clear_end_keyframe: bool = False,
    image_prompt: Optional[str] = None,
    video_prompt: Optional[str] = None,
    notes: Optional[str] = None,
) -> Shot:
    shot = require_shot(project, shot_id)
    if description is not None:
        shot.description = description
    if label is not None:
        shot.label = label
    if shot_type is not None:
        shot.shot_type = shot_type
    if camera_angle is not None:
        shot.camera_angle = camera_angle
    if camera_move is not None:
        shot.camera_move = camera_move
    if lens_composition is not None:
        shot.lens_composition = lens_composition
    if subject_action is not None:
        shot.subject_action = subject_action
    if dialogue_or_sound is not None:
        shot.dialogue_or_sound = dialogue_or_sound
    if clear_duration:
        shot.duration_s = None
    elif duration_s is not None:
        shot.duration_s = float(duration_s)
    if clear_prev:
        shot.prev_shot_id = None
    elif prev_shot_id is not None:
        if prev_shot_id and project.get_shot(prev_shot_id) is None:
            raise KeyError(f"Unknown prev_shot_id '{prev_shot_id}'")
        shot.prev_shot_id = prev_shot_id or None
    if clear_next:
        shot.next_shot_id = None
    elif next_shot_id is not None:
        if next_shot_id and project.get_shot(next_shot_id) is None:
            raise KeyError(f"Unknown next_shot_id '{next_shot_id}'")
        shot.next_shot_id = next_shot_id or None
    if clear_continuity_state:
        shot.continuity_state_id = None
    elif continuity_state_id is not None:
        shot.continuity_state_id = continuity_state_id or None
    if clear_start_keyframe:
        shot.start_keyframe_path = None
    elif start_keyframe_path is not None:
        shot.start_keyframe_path = start_keyframe_path or None
    if clear_end_keyframe:
        shot.end_keyframe_path = None
    elif end_keyframe_path is not None:
        shot.end_keyframe_path = end_keyframe_path or None
    if image_prompt is not None:
        shot.image_prompt = image_prompt
    if video_prompt is not None:
        shot.video_prompt = video_prompt
    if notes is not None:
        shot.notes = notes

    # Promote status when enough planning fields exist (same rule as interactive shots)
    if shot.anchor_ref_id and shot.shot_type and shot.camera_move and shot.subject_action:
        shot.status = "prompted"
    elif shot.anchor_ref_id:
        shot.status = "anchored"
    return shot


def approve_planning(project: Project, shot_id: str, *, approved_by: str = "jay") -> Shot:
    """Mark storyboard/shot plan approved. Does not set continuity_approved."""
    shot = require_shot(project, shot_id)
    shot.planning_approved = True
    shot.planning_approved_at = _now_iso()
    shot.planning_approved_by = approved_by
    return shot


def format_shot(shot: Shot, style=None) -> str:
    lines = [
        f"Shot {shot.id}  order={shot.order}  status={shot.status}",
        f"  label: {shot.label}",
        f"  description: {shot.description or '(none)'}",
        f"  scene_index: {shot.scene_index}",
        f"  shot_type: {shot.shot_type or '(unset)'}",
        f"  camera_angle: {shot.camera_angle or '(unset)'}",
        f"  camera_move: {shot.camera_move or '(unset)'}",
        f"  lens_composition: {shot.lens_composition or '(unset)'}",
        f"  action: {shot.subject_action or '(unset)'}",
        f"  dialogue_or_sound: {shot.dialogue_or_sound or '(none)'}",
        f"  duration_s: {shot.duration_s if shot.duration_s is not None else '(unset)'}",
        f"  characters: {shot.character_ids}",
        f"  location: {shot.location_id}",
        f"  props: {shot.prop_ids}",
        f"  continuity_state_id: {shot.continuity_state_id}",
        f"  prev → next: {shot.prev_shot_id} → {shot.next_shot_id}",
        f"  start_keyframe: {shot.start_keyframe_path or '(none)'}",
        f"  end_keyframe: {shot.end_keyframe_path or '(none)'}",
        f"  continuity_status: {shot.continuity_status}",
        f"  planning_approved: {shot.planning_approved}"
        + (f" by {shot.planning_approved_by} at {shot.planning_approved_at}" if shot.planning_approved else ""),
        f"  continuity_approved: {shot.continuity_approved}",
        f"  generation_complete: {shot.generation_complete}",
    ]
    if style is not None:
        lines.append(f"  image_prompt: {prompt_builder.effective_image_prompt(shot, style)}")
        lines.append(f"  video_prompt: {prompt_builder.effective_video_prompt(shot, style) or '(unset)'}")
    else:
        lines.append(f"  image_prompt (stored): {shot.image_prompt or '(empty → builder)'}")
        lines.append(f"  video_prompt (stored): {shot.video_prompt or '(empty)'}")
    if shot.notes:
        lines.append(f"  notes: {shot.notes}")
    return "\n".join(lines)


def summarize_shots(project: Project) -> str:
    lines = [f"{len(project.shots)} shot(s):"]
    for shot in sorted(project.shots, key=lambda s: s.order):
        plan = "plan_ok" if shot.planning_approved else "plan_open"
        cont = shot.continuity_status
        lines.append(
            f"  {shot.order:03d} {shot.id}  {shot.label!r}  "
            f"{shot.shot_type or '-'} / {shot.camera_angle or '-'} / {shot.camera_move or '-'}  "
            f"prev={shot.prev_shot_id or '-'} next={shot.next_shot_id or '-'}  "
            f"{plan}  cont={cont}"
        )
    return "\n".join(lines)
