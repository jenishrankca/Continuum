"""Continuity ledger and scene/shot state engine (Stage 4)."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .project import (
    CharacterState,
    ContinuityException,
    ContinuityState,
    LedgerHistoryEntry,
    LocationState,
    Project,
    PropState,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _append_history(
    project: Project,
    *,
    action: str,
    actor: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> LedgerHistoryEntry:
    """Append an immutable history row. Never mutates prior entries."""
    entry = LedgerHistoryEntry(
        entry_id=_new_id("hist"),
        ts=_now_iso(),
        action=action,
        actor=actor,
        summary=summary,
        payload=deepcopy(payload or {}),
    )
    project.ledger_history.append(entry)
    return entry


def get_state_for_scene(project: Project, scene_index: int) -> Optional[ContinuityState]:
    for state in project.continuity_states:
        if state.scope == "scene" and state.scene_index == scene_index:
            return state
    return None


def get_state_for_shot(project: Project, shot_id: str) -> Optional[ContinuityState]:
    for state in project.continuity_states:
        if state.scope == "shot" and state.shot_id == shot_id:
            return state
    shot = next((s for s in project.shots if s.id == shot_id), None)
    if shot and shot.continuity_state_id:
        for state in project.continuity_states:
            if state.state_id == shot.continuity_state_id:
                return state
    return None


def get_state_by_id(project: Project, state_id: str) -> Optional[ContinuityState]:
    for state in project.continuity_states:
        if state.state_id == state_id:
            return state
    return None


def ensure_scene_state(project: Project, scene_index: int, *, actor: str = "system") -> ContinuityState:
    existing = get_state_for_scene(project, scene_index)
    if existing:
        return existing
    if project.get_scene(scene_index) is None:
        raise ValueError(f"Unknown scene_index {scene_index}")
    now = _now_iso()
    state = ContinuityState(
        state_id=_new_id("state"),
        scope="scene",
        scene_index=scene_index,
        created_at=now,
        updated_at=now,
    )
    project.continuity_states.append(state)
    _append_history(
        project,
        action="create_state",
        actor=actor,
        summary=f"Created continuity state for scene {scene_index}",
        payload={"state_id": state.state_id, "scope": "scene", "scene_index": scene_index},
    )
    return state


def ensure_shot_state(project: Project, shot_id: str, *, actor: str = "system") -> ContinuityState:
    existing = get_state_for_shot(project, shot_id)
    if existing:
        return existing
    shot = next((s for s in project.shots if s.id == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot_id {shot_id}")
    now = _now_iso()
    state = ContinuityState(
        state_id=_new_id("state"),
        scope="shot",
        scene_index=shot.scene_index,
        shot_id=shot_id,
        created_at=now,
        updated_at=now,
    )
    project.continuity_states.append(state)
    shot.continuity_state_id = state.state_id
    _append_history(
        project,
        action="create_state",
        actor=actor,
        summary=f"Created continuity state for shot {shot_id}",
        payload={
            "state_id": state.state_id,
            "scope": "shot",
            "shot_id": shot_id,
            "scene_index": shot.scene_index,
        },
    )
    return state


def _require_bible_character(project: Project, character_id: str) -> None:
    if not any(c.id == character_id for c in project.characters):
        raise ValueError(f"Unknown character_id '{character_id}' (add via bible first)")


def _require_bible_location(project: Project, location_id: str) -> None:
    if not any(loc.id == location_id for loc in project.locations):
        raise ValueError(f"Unknown location_id '{location_id}' (add via bible first)")


def _require_bible_prop(project: Project, prop_id: str) -> None:
    if not any(p.id == prop_id for p in project.props):
        raise ValueError(f"Unknown prop_id '{prop_id}' (add via bible first)")


def set_character_state(
    project: Project,
    state: ContinuityState,
    *,
    character_id: str,
    wardrobe: Optional[str] = None,
    appearance: Optional[str] = None,
    holding_prop_ids: Optional[list[str]] = None,
    notes: Optional[str] = None,
    actor: str = "tech-lead",
) -> CharacterState:
    _require_bible_character(project, character_id)
    if holding_prop_ids is not None:
        for pid in holding_prop_ids:
            _require_bible_prop(project, pid)

    before = None
    target: CharacterState | None = None
    for cs in state.character_states:
        if cs.character_id == character_id:
            target = cs
            before = deepcopy(cs)
            break
    if target is None:
        target = CharacterState(character_id=character_id)
        state.character_states.append(target)

    if wardrobe is not None:
        target.wardrobe = wardrobe
    if appearance is not None:
        target.appearance = appearance
    if holding_prop_ids is not None:
        target.holding_prop_ids = list(holding_prop_ids)
    if notes is not None:
        target.notes = notes

    state.updated_at = _now_iso()
    _append_history(
        project,
        action="set_character_state",
        actor=actor,
        summary=f"Set character {character_id} on {state.state_id}",
        payload={
            "state_id": state.state_id,
            "before": before.__dict__ if before else None,
            "after": deepcopy(target).__dict__,
        },
    )
    return target


def set_location_state(
    project: Project,
    state: ContinuityState,
    *,
    location_id: str,
    time_of_day: Optional[str] = None,
    notes: Optional[str] = None,
    actor: str = "tech-lead",
) -> LocationState:
    _require_bible_location(project, location_id)
    before = deepcopy(state.location_state) if state.location_state else None
    if state.location_state is None or state.location_state.location_id != location_id:
        state.location_state = LocationState(location_id=location_id)
    if time_of_day is not None:
        state.location_state.time_of_day = time_of_day
    if notes is not None:
        state.location_state.notes = notes
    state.updated_at = _now_iso()
    _append_history(
        project,
        action="set_location_state",
        actor=actor,
        summary=f"Set location {location_id} on {state.state_id}",
        payload={
            "state_id": state.state_id,
            "before": before.__dict__ if before else None,
            "after": deepcopy(state.location_state).__dict__,
        },
    )
    return state.location_state


def set_prop_state(
    project: Project,
    state: ContinuityState,
    *,
    prop_id: str,
    location_note: Optional[str] = None,
    owner_character_id: Optional[str] = None,
    notes: Optional[str] = None,
    clear_owner: bool = False,
    actor: str = "tech-lead",
) -> PropState:
    _require_bible_prop(project, prop_id)
    if owner_character_id is not None:
        _require_bible_character(project, owner_character_id)

    before = None
    target: PropState | None = None
    for ps in state.prop_states:
        if ps.prop_id == prop_id:
            target = ps
            before = deepcopy(ps)
            break
    if target is None:
        target = PropState(prop_id=prop_id)
        state.prop_states.append(target)

    if location_note is not None:
        target.location_note = location_note
    if clear_owner:
        target.owner_character_id = None
    elif owner_character_id is not None:
        target.owner_character_id = owner_character_id
    if notes is not None:
        target.notes = notes

    state.updated_at = _now_iso()
    _append_history(
        project,
        action="set_prop_state",
        actor=actor,
        summary=f"Set prop {prop_id} on {state.state_id}",
        payload={
            "state_id": state.state_id,
            "before": before.__dict__ if before else None,
            "after": deepcopy(target).__dict__,
        },
    )
    return target


def copy_state(
    project: Project,
    *,
    from_state: ContinuityState,
    to_scope: str,
    to_scene_index: Optional[int] = None,
    to_shot_id: Optional[str] = None,
    actor: str = "tech-lead",
) -> ContinuityState:
    """Copy continuity facts to a new scene/shot scope (transition helper)."""
    if to_scope == "scene":
        if to_scene_index is None:
            raise ValueError("to_scene_index required for scene scope")
        dest = ensure_scene_state(project, to_scene_index, actor=actor)
    elif to_scope == "shot":
        if not to_shot_id:
            raise ValueError("to_shot_id required for shot scope")
        dest = ensure_shot_state(project, to_shot_id, actor=actor)
    else:
        raise ValueError(f"Unknown scope '{to_scope}'")

    dest.character_states = deepcopy(from_state.character_states)
    dest.location_state = deepcopy(from_state.location_state)
    dest.prop_states = deepcopy(from_state.prop_states)
    dest.notes = from_state.notes
    dest.updated_at = _now_iso()
    _append_history(
        project,
        action="transition",
        actor=actor,
        summary=f"Copied state {from_state.state_id} -> {dest.state_id}",
        payload={
            "from_state_id": from_state.state_id,
            "to_state_id": dest.state_id,
            "to_scope": to_scope,
            "to_scene_index": to_scene_index,
            "to_shot_id": to_shot_id,
        },
    )
    return dest


def add_exception(
    project: Project,
    *,
    from_scope: str,
    from_ref: str,
    to_scope: str,
    to_ref: str,
    reason: str,
    fields_changed: list[str] | None = None,
    actor: str = "tech-lead",
) -> ContinuityException:
    if not reason.strip():
        raise ValueError("Exception reason is required")
    exc = ContinuityException(
        exception_id=_new_id("exc"),
        from_scope=from_scope,
        from_ref=str(from_ref),
        to_scope=to_scope,
        to_ref=str(to_ref),
        reason=reason.strip(),
        fields_changed=list(fields_changed or []),
        created_at=_now_iso(),
    )
    project.continuity_exceptions.append(exc)
    _append_history(
        project,
        action="add_exception",
        actor=actor,
        summary=f"Exception {exc.exception_id}: {exc.reason}",
        payload=deepcopy(exc.__dict__),
    )
    return exc


def approve_exception(
    project: Project,
    exception_id: str,
    *,
    approved_by: str = "jay",
    actor: str | None = None,
) -> ContinuityException:
    exc = next((e for e in project.continuity_exceptions if e.exception_id == exception_id), None)
    if exc is None:
        raise ValueError(f"Unknown exception_id '{exception_id}'")
    if exc.approved:
        raise ValueError(f"Exception {exception_id} already approved at {exc.approved_at}")
    # History captures prior + after; do not rewrite earlier rows
    before = deepcopy(exc.__dict__)
    exc.approved = True
    exc.approved_at = date.today().isoformat()
    exc.approved_by = approved_by
    who = actor or approved_by
    _append_history(
        project,
        action="approve_exception",
        actor=who,
        summary=f"Approved exception {exception_id} by {approved_by}",
        payload={"before": before, "after": deepcopy(exc.__dict__)},
    )
    return exc


def query_character(project: Project, character_id: str) -> list[dict[str, Any]]:
    """Where a character appears across ledger states."""
    _require_bible_character(project, character_id)
    rows: list[dict[str, Any]] = []
    for state in project.continuity_states:
        for cs in state.character_states:
            if cs.character_id == character_id:
                rows.append(
                    {
                        "state_id": state.state_id,
                        "scope": state.scope,
                        "scene_index": state.scene_index,
                        "shot_id": state.shot_id,
                        "wardrobe": cs.wardrobe,
                        "appearance": cs.appearance,
                        "holding_prop_ids": list(cs.holding_prop_ids),
                        "notes": cs.notes,
                    }
                )
    return rows


def query_prop(project: Project, prop_id: str) -> list[dict[str, Any]]:
    _require_bible_prop(project, prop_id)
    rows: list[dict[str, Any]] = []
    for state in project.continuity_states:
        for ps in state.prop_states:
            if ps.prop_id == prop_id:
                rows.append(
                    {
                        "state_id": state.state_id,
                        "scope": state.scope,
                        "scene_index": state.scene_index,
                        "shot_id": state.shot_id,
                        "location_note": ps.location_note,
                        "owner_character_id": ps.owner_character_id,
                        "notes": ps.notes,
                    }
                )
    return rows


def summarize_ledger(project: Project) -> str:
    lines = [
        f"Ledger for {project.slug} (schema {project.schema_version})",
        f"  states: {len(project.continuity_states)}",
        f"  exceptions: {len(project.continuity_exceptions)} "
        f"({sum(1 for e in project.continuity_exceptions if e.approved)} approved)",
        f"  history: {len(project.ledger_history)} entries",
    ]
    for state in sorted(
        project.continuity_states,
        key=lambda s: (s.scope, s.scene_index if s.scene_index is not None else -1, s.shot_id or ""),
    ):
        loc = state.location_state.location_id if state.location_state else "—"
        lines.append(
            f"  - {state.state_id} [{state.scope}] "
            f"scene={state.scene_index} shot={state.shot_id or '—'} "
            f"chars={len(state.character_states)} props={len(state.prop_states)} loc={loc}"
        )
    for exc in project.continuity_exceptions:
        flag = "approved" if exc.approved else "pending"
        lines.append(
            f"  ! {exc.exception_id} [{flag}] "
            f"{exc.from_scope}:{exc.from_ref} -> {exc.to_scope}:{exc.to_ref}: {exc.reason}"
        )
    return "\n".join(lines)


def format_state(state: ContinuityState) -> str:
    lines = [
        f"State {state.state_id} scope={state.scope} "
        f"scene={state.scene_index} shot={state.shot_id or '—'}",
        f"  updated={state.updated_at}",
    ]
    if state.notes:
        lines.append(f"  notes: {state.notes}")
    if state.location_state:
        ls = state.location_state
        lines.append(
            f"  location {ls.location_id}: time={ls.time_of_day or '—'} notes={ls.notes or '—'}"
        )
    for cs in state.character_states:
        hold = ",".join(cs.holding_prop_ids) if cs.holding_prop_ids else "—"
        lines.append(
            f"  character {cs.character_id}: wardrobe={cs.wardrobe or '—'} "
            f"appearance={cs.appearance or '—'} holding={hold}"
        )
    for ps in state.prop_states:
        lines.append(
            f"  prop {ps.prop_id}: at={ps.location_note or '—'} "
            f"owner={ps.owner_character_id or '—'} notes={ps.notes or '—'}"
        )
    return "\n".join(lines)
