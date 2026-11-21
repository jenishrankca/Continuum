"""Continuity-aware reference assembly for image generation (vision §8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import bible, ledger, prompt_builder
from ..project import ContinuityPackRef, ContinuityState, Project, Shot, StyleBible


@dataclass
class ContinuityPack:
    shot_id: str
    prompt: str
    negative_prompt: str
    style_phrase: str
    references: list[ContinuityPackRef] = field(default_factory=list)
    wardrobe_notes: list[str] = field(default_factory=list)
    continuity_state_id: Optional[str] = None
    summary: str = ""

    @property
    def paths(self) -> list[str]:
        return [r.path for r in self.references if r.path]


def _best_asset_path(assets) -> tuple[Optional[str], Optional[str], bool]:
    """Prefer approved styled → approved raw → any styled → any raw."""
    approved = [a for a in assets if a.approved]
    pool = approved or list(assets)
    for a in pool:
        if a.styled_path:
            return a.styled_path, a.asset_id, a.approved
    for a in pool:
        if a.raw_path:
            return a.raw_path, a.asset_id, a.approved
    return None, None, False


def _append_entity_refs(
    refs: list[ContinuityPackRef],
    *,
    role: str,
    entity_id: str,
    assets,
    notes: str = "",
) -> None:
    path, asset_id, approved = _best_asset_path(assets)
    refs.append(
        ContinuityPackRef(
            role=role,
            entity_id=entity_id,
            asset_id=asset_id,
            path=path,
            approved=approved,
            notes=notes or ("missing asset" if path is None else ""),
        )
    )


def assemble_continuity_pack(project: Project, shot_id: str) -> ContinuityPack:
    shot = project.get_shot(shot_id)
    if shot is None:
        raise KeyError(f"Unknown shot id '{shot_id}'")

    style: StyleBible = project.style
    prompt = prompt_builder.effective_image_prompt(shot, style)
    negative = "blurry, watermark, text overlay, deformed hands"
    refs: list[ContinuityPackRef] = []
    wardrobe_notes: list[str] = []

    state: Optional[ContinuityState] = ledger.get_state_for_shot(project, shot_id)
    if state is None and shot.scene_index is not None:
        state = ledger.get_state_for_scene(project, shot.scene_index)

    # Characters + wardrobe from ledger when present
    char_ids = list(shot.character_ids)
    if state:
        for cs in state.character_states:
            if cs.character_id not in char_ids:
                char_ids.append(cs.character_id)
            note = ", ".join(
                p for p in [cs.wardrobe, cs.appearance, cs.notes] if p
            )
            if note:
                wardrobe_notes.append(f"{cs.character_id}: {note}")

    for cid in char_ids:
        ent = bible.get_character(project, cid)
        if ent is None:
            refs.append(
                ContinuityPackRef(
                    role="character",
                    entity_id=cid,
                    notes="character id not in bible",
                )
            )
            continue
        _append_entity_refs(
            refs,
            role="character",
            entity_id=cid,
            assets=ent.assets,
            notes=ent.appearance_notes or ent.wardrobe_notes,
        )

    loc_id = shot.location_id
    if state and state.location_state and state.location_state.location_id:
        loc_id = loc_id or state.location_state.location_id
    if loc_id:
        ent = bible.get_location(project, loc_id)
        if ent is None:
            refs.append(
                ContinuityPackRef(role="location", entity_id=loc_id, notes="location not in bible")
            )
        else:
            _append_entity_refs(
                refs,
                role="location",
                entity_id=loc_id,
                assets=ent.assets,
                notes=ent.lighting_notes or "",
            )

    prop_ids = list(shot.prop_ids)
    if state:
        for ps in state.prop_states:
            if ps.prop_id not in prop_ids:
                prop_ids.append(ps.prop_id)
    for pid in prop_ids:
        ent = bible.get_prop(project, pid)
        if ent is None:
            refs.append(ContinuityPackRef(role="prop", entity_id=pid, notes="prop not in bible"))
            continue
        _append_entity_refs(refs, role="prop", entity_id=pid, assets=ent.assets)

    # Previous shot final frame preference: end_keyframe → raw_frame of prev
    if shot.prev_shot_id:
        prev = project.get_shot(shot.prev_shot_id)
        if prev:
            prev_path = prev.end_keyframe_path or prev.raw_frame_path
            refs.append(
                ContinuityPackRef(
                    role="prev_frame",
                    entity_id=prev.id,
                    path=prev_path,
                    approved=bool(prev.end_keyframe_path),
                    notes="previous shot end/raw frame",
                )
            )

    if shot.start_keyframe_path:
        refs.append(
            ContinuityPackRef(
                role="keyframe_start",
                path=shot.start_keyframe_path,
                approved=True,
                notes="shot start keyframe",
            )
        )
    if shot.end_keyframe_path:
        refs.append(
            ContinuityPackRef(
                role="keyframe_end",
                path=shot.end_keyframe_path,
                approved=True,
                notes="shot end keyframe",
            )
        )

    if shot.raw_frame_path:
        refs.append(
            ContinuityPackRef(
                role="raw_frame",
                path=shot.raw_frame_path,
                approved=False,
                notes="source frame for shot",
            )
        )

    if shot.anchor_ref_id:
        ref = project.get_ref(shot.anchor_ref_id)
        if ref:
            path = ref.styled_frame_path or ref.raw_frame_path
            refs.append(
                ContinuityPackRef(
                    role="style",
                    entity_id=ref.ref_id,
                    path=path,
                    approved=ref.restyle_status == "completed",
                    notes=f"anchor {ref.tag}: {ref.description}",
                )
            )

    present = sum(1 for r in refs if r.path)
    approved = sum(1 for r in refs if r.path and r.approved)
    summary = (
        f"shot={shot_id} refs={present}/{len(refs)} with_path "
        f"approved={approved} wardrobe_notes={len(wardrobe_notes)} "
        f"state={state.state_id if state else 'none'}"
    )
    if wardrobe_notes:
        prompt = f"{prompt}. Continuity wardrobe: " + "; ".join(wardrobe_notes)

    return ContinuityPack(
        shot_id=shot_id,
        prompt=prompt,
        negative_prompt=negative,
        style_phrase=style.style_phrase,
        references=refs,
        wardrobe_notes=wardrobe_notes,
        continuity_state_id=state.state_id if state else shot.continuity_state_id,
        summary=summary,
    )


def format_pack(pack: ContinuityPack) -> str:
    lines = [
        f"Continuity pack for {pack.shot_id}",
        f"  summary: {pack.summary}",
        f"  state: {pack.continuity_state_id or '(none)'}",
        f"  style: {pack.style_phrase}",
        f"  prompt: {pack.prompt[:200]}{'…' if len(pack.prompt) > 200 else ''}",
        f"  negative: {pack.negative_prompt}",
        "  references:",
    ]
    for r in pack.references:
        flag = "ok" if r.approved else "draft"
        lines.append(
            f"    - {r.role} entity={r.entity_id or '—'} asset={r.asset_id or '—'} "
            f"[{flag}] path={r.path or '(missing)'} {r.notes}"
        )
    if pack.wardrobe_notes:
        lines.append("  wardrobe:")
        for w in pack.wardrobe_notes:
            lines.append(f"    - {w}")
    return "\n".join(lines)
