"""Character / Location / Prop bible management (Stage 3)."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from .project import (
    Character,
    Location,
    Project,
    Prop,
    ReferenceAsset,
    ReferenceImage,
    Shot,
    slugify,
)

EntityKind = Literal["character", "location", "prop"]


def _asset_from_ref(ref: ReferenceImage) -> ReferenceAsset:
    return ReferenceAsset(
        asset_id=f"{ref.ref_id}-asset",
        raw_path=ref.raw_frame_path,
        styled_path=ref.styled_frame_path,
        source_ref_id=ref.ref_id,
        approved=ref.restyle_status == "completed",
        approved_at=date.today().isoformat() if ref.restyle_status == "completed" else None,
        notes=ref.description,
    )


def _name_from_ref(ref: ReferenceImage) -> str:
    if ref.description.strip():
        return ref.description.strip().split(",")[0].strip()[:80]
    return ref.ref_id.replace("_", " ")


def promote_from_reference_images(project: Project) -> dict[str, int]:
    """Create bible entities from Phase 1 reference_images (additive; skips existing ids)."""
    created = {"character": 0, "location": 0, "prop": 0, "skipped": 0}
    existing_char = {c.id for c in project.characters}
    existing_loc = {loc.id for loc in project.locations}
    existing_prop = {p.id for p in project.props}

    for ref in project.reference_images:
        asset = _asset_from_ref(ref)
        if ref.tag == "character":
            if ref.ref_id in existing_char:
                created["skipped"] += 1
                continue
            project.characters.append(
                Character(
                    id=ref.ref_id,
                    name=_name_from_ref(ref),
                    description=ref.description,
                    assets=[asset],
                )
            )
            existing_char.add(ref.ref_id)
            created["character"] += 1
        elif ref.tag == "set":
            if ref.ref_id in existing_loc:
                created["skipped"] += 1
                continue
            project.locations.append(
                Location(
                    id=ref.ref_id,
                    name=_name_from_ref(ref),
                    description=ref.description,
                    assets=[asset],
                )
            )
            existing_loc.add(ref.ref_id)
            created["location"] += 1
        elif ref.tag == "prop":
            if ref.ref_id in existing_prop:
                created["skipped"] += 1
                continue
            project.props.append(
                Prop(
                    id=ref.ref_id,
                    name=_name_from_ref(ref),
                    description=ref.description,
                    assets=[asset],
                )
            )
            existing_prop.add(ref.ref_id)
            created["prop"] += 1
        else:
            created["skipped"] += 1

    _link_shots_from_anchors(project)
    return created


def _link_shots_from_anchors(project: Project) -> None:
    char_ids = {c.id for c in project.characters}
    loc_ids = {loc.id for loc in project.locations}
    prop_ids = {p.id for p in project.props}
    for shot in project.shots:
        if not shot.anchor_ref_id:
            continue
        aid = shot.anchor_ref_id
        if aid in char_ids and aid not in shot.character_ids:
            shot.character_ids.append(aid)
        if aid in loc_ids and shot.location_id is None:
            shot.location_id = aid
        if aid in prop_ids and aid not in shot.prop_ids:
            shot.prop_ids.append(aid)


def get_character(project: Project, entity_id: str) -> Optional[Character]:
    for c in project.characters:
        if c.id == entity_id:
            return c
    return None


def get_location(project: Project, entity_id: str) -> Optional[Location]:
    for loc in project.locations:
        if loc.id == entity_id:
            return loc
    return None


def get_prop(project: Project, entity_id: str) -> Optional[Prop]:
    for p in project.props:
        if p.id == entity_id:
            return p
    return None


def add_character(
    project: Project,
    *,
    entity_id: str,
    name: str,
    description: str = "",
) -> Character:
    eid = slugify(entity_id)
    if get_character(project, eid):
        raise ValueError(f"Character '{eid}' already exists")
    char = Character(id=eid, name=name, description=description)
    project.characters.append(char)
    return char


def add_location(
    project: Project,
    *,
    entity_id: str,
    name: str,
    description: str = "",
) -> Location:
    eid = slugify(entity_id)
    if get_location(project, eid):
        raise ValueError(f"Location '{eid}' already exists")
    loc = Location(id=eid, name=name, description=description)
    project.locations.append(loc)
    return loc


def add_prop(
    project: Project,
    *,
    entity_id: str,
    name: str,
    description: str = "",
) -> Prop:
    eid = slugify(entity_id)
    if get_prop(project, eid):
        raise ValueError(f"Prop '{eid}' already exists")
    prop = Prop(id=eid, name=name, description=description)
    project.props.append(prop)
    return prop


def _entity_assets(project: Project, kind: EntityKind, entity_id: str) -> list[ReferenceAsset]:
    if kind == "character":
        ent = get_character(project, entity_id)
        if not ent:
            raise ValueError(f"Unknown character '{entity_id}'")
        return ent.assets
    if kind == "location":
        ent = get_location(project, entity_id)
        if not ent:
            raise ValueError(f"Unknown location '{entity_id}'")
        return ent.assets
    ent = get_prop(project, entity_id)
    if not ent:
        raise ValueError(f"Unknown prop '{entity_id}'")
    return ent.assets


def attach_asset(
    project: Project,
    *,
    kind: EntityKind,
    entity_id: str,
    asset_id: str,
    raw_path: str,
    styled_path: Optional[str] = None,
    source_ref_id: Optional[str] = None,
    notes: str = "",
) -> ReferenceAsset:
    """Attach a new reference asset. Never overwrites an approved asset's paths."""
    assets = _entity_assets(project, kind, entity_id)
    for existing in assets:
        if existing.asset_id == asset_id:
            if existing.approved:
                raise ValueError(
                    f"Asset '{asset_id}' is approved; refusing to overwrite. "
                    "Use a new --asset-id instead."
                )
            existing.raw_path = raw_path
            existing.styled_path = styled_path
            existing.source_ref_id = source_ref_id
            existing.notes = notes or existing.notes
            return existing
    asset = ReferenceAsset(
        asset_id=asset_id,
        raw_path=raw_path,
        styled_path=styled_path,
        source_ref_id=source_ref_id,
        notes=notes,
    )
    assets.append(asset)
    return asset


def attach_from_reference(
    project: Project,
    *,
    kind: EntityKind,
    entity_id: str,
    ref_id: str,
) -> ReferenceAsset:
    ref = project.get_ref(ref_id)
    if not ref:
        raise ValueError(f"Unknown reference_image '{ref_id}'")
    return attach_asset(
        project,
        kind=kind,
        entity_id=entity_id,
        asset_id=f"{ref_id}-asset",
        raw_path=ref.raw_frame_path,
        styled_path=ref.styled_frame_path,
        source_ref_id=ref.ref_id,
        notes=ref.description,
    )


def approve_asset(
    project: Project,
    *,
    kind: EntityKind,
    entity_id: str,
    asset_id: str,
) -> ReferenceAsset:
    assets = _entity_assets(project, kind, entity_id)
    for asset in assets:
        if asset.asset_id == asset_id:
            asset.approved = True
            asset.approved_at = date.today().isoformat()
            return asset
    raise ValueError(f"Unknown asset '{asset_id}' on {kind} '{entity_id}'")


def approve_entity(project: Project, *, kind: EntityKind, entity_id: str) -> None:
    if kind == "character":
        ent = get_character(project, entity_id)
    elif kind == "location":
        ent = get_location(project, entity_id)
    else:
        ent = get_prop(project, entity_id)
    if not ent:
        raise ValueError(f"Unknown {kind} '{entity_id}'")
    ent.approved = True


def link_shot(
    project: Project,
    *,
    shot_id: str,
    character_ids: Optional[list[str]] = None,
    location_id: Optional[str] = None,
    prop_ids: Optional[list[str]] = None,
    replace: bool = False,
) -> Shot:
    shot = next((s for s in project.shots if s.id == shot_id), None)
    if not shot:
        raise ValueError(f"Unknown shot '{shot_id}'")
    if character_ids is not None:
        for cid in character_ids:
            if not get_character(project, cid):
                raise ValueError(f"Unknown character '{cid}'")
        shot.character_ids = (
            list(character_ids) if replace else sorted(set(shot.character_ids) | set(character_ids))
        )
    if location_id is not None:
        if location_id == "":
            shot.location_id = None
        else:
            if not get_location(project, location_id):
                raise ValueError(f"Unknown location '{location_id}'")
            shot.location_id = location_id
    if prop_ids is not None:
        for pid in prop_ids:
            if not get_prop(project, pid):
                raise ValueError(f"Unknown prop '{pid}'")
        shot.prop_ids = list(prop_ids) if replace else sorted(set(shot.prop_ids) | set(prop_ids))
    return shot


def summarize_bible(project: Project) -> str:
    lines = [
        f"Characters: {len(project.characters)}",
        f"Locations:  {len(project.locations)}",
        f"Props:      {len(project.props)}",
        "",
    ]
    for c in project.characters:
        approved_assets = sum(1 for a in c.assets if a.approved)
        flag = "approved" if c.approved else "draft"
        lines.append(
            f"  character {c.id}: {c.name} [{flag}] "
            f"assets={len(c.assets)} approved_assets={approved_assets}"
        )
    for loc in project.locations:
        approved_assets = sum(1 for a in loc.assets if a.approved)
        flag = "approved" if loc.approved else "draft"
        lines.append(
            f"  location  {loc.id}: {loc.name} [{flag}] "
            f"assets={len(loc.assets)} approved_assets={approved_assets}"
        )
    for p in project.props:
        approved_assets = sum(1 for a in p.assets if a.approved)
        flag = "approved" if p.approved else "draft"
        lines.append(
            f"  prop      {p.id}: {p.name} [{flag}] "
            f"assets={len(p.assets)} approved_assets={approved_assets}"
        )
    return "\n".join(lines)
