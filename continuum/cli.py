"""CLI entry point: python -m continuum <command> <slug> [options]"""
from __future__ import annotations

import argparse
from pathlib import Path

from .project import Project, StyleBible, SCHEMA_VERSION
from . import bible
from . import detect, review, shots as shots_module, lint, render_markdown, render_html
from . import migrate as migrate_module
from . import paths
from .restyle import get_provider
from .envfile import load_dotenv


def cmd_init(args: argparse.Namespace) -> None:
    root = Path.cwd()
    slug = args.slug

    if Project.yaml_path(root, slug).exists():
        print(f"Project '{slug}' already exists at {Project.project_dir(root, slug)}")
        return

    source = Path(args.source)
    if not source.exists():
        print(f"Source video not found: {source}")
        return

    style = StyleBible(
        project_name=args.name or slug,
        style_phrase=args.style,
        lighting_phrase=args.lighting,
        grain_grade_phrase=args.grade,
        genre_mode=args.genre,
        default_restyle_provider=args.provider,
    )
    # Store relative when under Continuum root; absolute otherwise (external media)
    stored_source = paths.to_stored(root, source.resolve()) or str(source.resolve())
    project = Project(
        schema_version=SCHEMA_VERSION,
        slug=slug,
        style=style,
        source_video_path=stored_source,
    )
    project.save(root)
    print(f"Created project '{slug}' at {Project.project_dir(root, slug)}")
    print("Next: `ingest`")


def cmd_ingest(args: argparse.Namespace) -> None:
    root = Path.cwd()
    project = Project.load(root, args.slug)
    frames_dir = Project.project_dir(root, args.slug) / "frames" / "raw"
    video_path = Path(project.source_video_path)

    print(f"Detecting scenes in {video_path} (threshold={args.threshold})...")
    scenes = detect.ingest(
        video_path, frames_dir, threshold=args.threshold, candidates_per_scene=args.candidates_per_scene
    )
    project.scenes = scenes
    project.save(root)
    print(f"Detected {len(scenes)} scene(s). Run `review` next.")


def cmd_review(args: argparse.Namespace) -> None:
    review.review_project(Path.cwd(), args.slug)


def cmd_restyle(args: argparse.Namespace) -> None:
    root = Path.cwd()
    project = Project.load(root, args.slug)
    provider_name = args.provider or project.style.default_restyle_provider
    provider = get_provider(provider_name)
    styled_dir = Project.project_dir(root, args.slug) / "styled"

    if args.check:
        if provider_name != "manual":
            print("--check only applies to the manual provider.")
            return
        changed = 0
        for ref in project.reference_images:
            if ref.restyle_status != "pending_manual" or not ref.styled_frame_path:
                continue
            if provider.check(Path(ref.styled_frame_path)):
                ref.restyle_status = "completed"
                changed += 1
        project.save(root)
        print(f"{changed} reference image(s) marked completed.")
        return

    if not project.reference_images:
        print("No reference images yet. Run `review` and flag some with `r <tag> <ref_id> <description>` first.")
        return

    for ref in project.reference_images:
        if ref.restyle_status == "completed":
            continue
        dest = styled_dir / f"{ref.ref_id}.jpg"
        result = provider.restyle(Path(ref.raw_frame_path), project.style.style_phrase, dest)
        ref.styled_frame_path = str(result.output_path)
        ref.restyle_status = result.status
        ref.restyle_provider = result.provider
        print(f"{ref.ref_id}: {result.status} - {result.message}")

    project.save(root)
    if provider_name == "manual":
        print("\nRun `restyle --check` after you've manually restyled and overwritten the files above.")


def cmd_shots(args: argparse.Namespace) -> None:
    shots_module.assign_shots(Path.cwd(), args.slug)


def cmd_generate_shotlist(args: argparse.Namespace) -> None:
    root = Path.cwd()
    project = Project.load(root, args.slug)

    warnings = lint.lint_project(project)
    if warnings:
        print(f"{len(warnings)} lint warning(s):")
        for w in warnings:
            print(f"  [{w.shot_id}] {w.message}")
        if args.strict:
            print("\n--strict set: fix the warnings above before generating.")
            return
        print()

    out_dir = Project.project_dir(root, args.slug) / "output"
    md_path = out_dir / "shotlist.md"
    html_path = out_dir / "storyboard.html"
    render_markdown.render_markdown(project, md_path)
    render_html.render_storyboard(project, html_path)
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")


def cmd_status(args: argparse.Namespace) -> None:
    root = Path.cwd()
    project = Project.load(root, args.slug)

    total_scenes = len(project.scenes)
    reviewed = sum(1 for s in project.scenes if s.reviewed)
    kept = sum(1 for s in project.scenes if s.kept)
    refs = len(project.reference_images)
    refs_done = sum(1 for r in project.reference_images if r.restyle_status == "completed")
    shots_total = len(project.shots)
    shots_prompted = sum(1 for s in project.shots if s.status == "prompted")

    print(f"Project: {project.style.project_name} ({project.slug})")
    print(f"Schema:      {project.schema_version}")
    print(f"Scenes:      {reviewed}/{total_scenes} reviewed, {kept} kept")
    print(f"References:  {refs_done}/{refs} restyled  (target 8-12 total)")
    print(f"Bible:       {len(project.characters)} characters, "
          f"{len(project.locations)} locations, {len(project.props)} props")
    print(f"Shots:       {shots_prompted}/{shots_total} fully detailed")


def cmd_migrate(args: argparse.Namespace) -> None:
    root = Path.cwd()
    report = migrate_module.migrate_project(root, args.slug, dry_run=args.dry_run)
    mode = "dry-run" if report.dry_run else "applied"
    print(f"Migrate {report.slug} ({mode}): schema {report.from_version} -> {report.to_version}")
    print(f"Paths rewritten: {report.paths_rewritten}")
    for line in report.messages[:40]:
        print(f"  {line}")
    if len(report.messages) > 40:
        print(f"  ... and {len(report.messages) - 40} more")


def cmd_dashboard(args: argparse.Namespace) -> None:
    from .dashboard import run_dashboard

    run_dashboard(host=args.host, port=args.port, root=Path.cwd())


def cmd_studio_dashboard(args: argparse.Namespace) -> None:
    from . import studio_dashboard as studio_dash

    root = Path.cwd()
    if args.serve:
        path = studio_dash.rebuild(root)
        print(f"Studio dashboard: {path}")
        print(f"Serving http://{args.host}:{args.port}/ (Ctrl+C to stop)")
        studio_dash.serve_dashboard(root, host=args.host, port=args.port, rebuild_first=False)
        return

    if args.open:
        path = studio_dash.open_dashboard(root, rebuild_first=True)
        print(f"Opened {path.resolve()}")
        return

    # Default / --rebuild: regenerate company/dashboard/
    path = studio_dash.rebuild(root)
    print(f"Wrote {path}")
    print(f"Also wrote {studio_dash.dashboard_data_js_path(root)}")
    print(f"Open: {path.resolve().as_uri()}")
    print("Or: python -m continuum studio-dashboard --open")


def cmd_bible(args: argparse.Namespace) -> None:
    root = Path.cwd()
    project = Project.load(root, args.slug)
    action = args.bible_action

    if action == "list":
        print(bible.summarize_bible(project))
        return

    if action == "promote":
        counts = bible.promote_from_reference_images(project)
        if not args.dry_run:
            project.save(root)
        mode = "dry-run" if args.dry_run else "saved"
        print(
            f"Promote ({mode}): +{counts['character']} characters, "
            f"+{counts['location']} locations, +{counts['prop']} props "
            f"(skipped {counts['skipped']})"
        )
        if not args.dry_run:
            print(bible.summarize_bible(project))
        return

    if action == "add-character":
        ent = bible.add_character(
            project, entity_id=args.id, name=args.name, description=args.description or ""
        )
        project.save(root)
        print(f"Added character {ent.id}: {ent.name}")
        return

    if action == "add-location":
        ent = bible.add_location(
            project, entity_id=args.id, name=args.name, description=args.description or ""
        )
        project.save(root)
        print(f"Added location {ent.id}: {ent.name}")
        return

    if action == "add-prop":
        ent = bible.add_prop(
            project, entity_id=args.id, name=args.name, description=args.description or ""
        )
        project.save(root)
        print(f"Added prop {ent.id}: {ent.name}")
        return

    if action == "attach-ref":
        asset = bible.attach_from_reference(
            project, kind=args.entity, entity_id=args.id, ref_id=args.ref
        )
        project.save(root)
        print(f"Attached asset {asset.asset_id} to {args.entity} {args.id}")
        return

    if action == "approve-asset":
        asset = bible.approve_asset(
            project, kind=args.entity, entity_id=args.id, asset_id=args.asset
        )
        project.save(root)
        print(f"Approved asset {asset.asset_id} on {args.entity} {args.id}")
        return

    if action == "approve-entity":
        bible.approve_entity(project, kind=args.entity, entity_id=args.id)
        project.save(root)
        print(f"Approved {args.entity} {args.id}")
        return

    if action == "link-shot":
        chars = args.character or []
        props = args.prop or []
        shot = bible.link_shot(
            project,
            shot_id=args.shot,
            character_ids=chars or None,
            location_id=args.location,
            prop_ids=props or None,
            replace=args.replace,
        )
        project.save(root)
        print(
            f"Linked {shot.id}: characters={shot.character_ids} "
            f"location={shot.location_id} props={shot.prop_ids}"
        )
        return

    raise SystemExit(f"Unknown bible action: {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="continuum")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a new project from a source .mp4")
    p_init.add_argument("slug")
    p_init.add_argument("--source", required=True, help="Path to the source .mp4")
    p_init.add_argument("--style", required=True, help="Locked style phrase (e.g. 'A24 horror')")
    p_init.add_argument("--lighting", required=True, help="Locked lighting phrase")
    p_init.add_argument("--grade", required=True, help="Locked film grain/grade phrase")
    p_init.add_argument("--name", help="Display project name (defaults to slug)")
    p_init.add_argument("--genre", choices=["drama", "comedy"], default="drama")
    p_init.add_argument("--provider", choices=["manual", "gemini", "local"], default="manual")
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser("ingest", help="Detect scenes and extract candidate frames")
    p_ingest.add_argument("slug")
    p_ingest.add_argument("--threshold", type=float, default=27.0)
    p_ingest.add_argument("--candidates-per-scene", type=int, default=3)
    p_ingest.set_defaults(func=cmd_ingest)

    p_review = sub.add_parser("review", help="Interactively keep/skip/reference-flag detected scenes")
    p_review.add_argument("slug")
    p_review.set_defaults(func=cmd_review)

    p_restyle = sub.add_parser("restyle", help="Restyle curated reference images with the locked style phrase")
    p_restyle.add_argument("slug")
    p_restyle.add_argument("--provider", choices=["manual", "gemini", "local"], default=None)
    p_restyle.add_argument("--check", action="store_true", help="Check manual restyles for completion")
    p_restyle.set_defaults(func=cmd_restyle)

    p_shots = sub.add_parser("shots", help="Assign shot type/camera/action/anchor per kept shot")
    p_shots.add_argument("slug")
    p_shots.set_defaults(func=cmd_shots)

    p_gen = sub.add_parser("generate-shotlist", help="Lint + render the markdown shot list and HTML storyboard")
    p_gen.add_argument("slug")
    p_gen.add_argument("--strict", action="store_true", help="Abort on lint warnings")
    p_gen.set_defaults(func=cmd_generate_shotlist)

    p_status = sub.add_parser("status", help="Show progress summary")
    p_status.add_argument("slug")
    p_status.set_defaults(func=cmd_status)

    p_migrate = sub.add_parser(
        "migrate",
        help="Rewrite paths, promote bible entities, bump schema_version",
    )
    p_migrate.add_argument("slug")
    p_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing project.yaml",
    )
    p_migrate.set_defaults(func=cmd_migrate)

    p_dash = sub.add_parser(
        "dashboard",
        help="Open a local browser dashboard (http://127.0.0.1:8765 by default)",
    )
    p_dash.add_argument("--host", default="127.0.0.1")
    p_dash.add_argument("--port", type=int, default=8765)
    p_dash.set_defaults(func=cmd_dashboard)

    p_studio = sub.add_parser(
        "studio-dashboard",
        help="Build/open local Studio CEO HTML under company/dashboard/ (file://)",
    )
    p_studio.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate index.html + data.js (default action)",
    )
    p_studio.add_argument(
        "--open",
        action="store_true",
        help="Rebuild and open company/dashboard/index.html in the browser",
    )
    p_studio.add_argument(
        "--serve",
        action="store_true",
        help="Serve company/dashboard/ on a tiny local HTTP server",
    )
    p_studio.add_argument("--host", default="127.0.0.1")
    p_studio.add_argument(
        "--port",
        type=int,
        default=8766,
        help="Port for --serve (default 8766; product dashboard stays on 8765)",
    )
    p_studio.set_defaults(func=cmd_studio_dashboard)

    p_bible = sub.add_parser("bible", help="Manage character / location / prop bible")
    bible_sub = p_bible.add_subparsers(dest="bible_action", required=True)

    p_list = bible_sub.add_parser("list", help="List bible entities")
    p_list.add_argument("slug")
    p_list.set_defaults(func=cmd_bible)

    p_promote = bible_sub.add_parser(
        "promote", help="Create bible entities from Phase 1 reference_images"
    )
    p_promote.add_argument("slug")
    p_promote.add_argument("--dry-run", action="store_true")
    p_promote.set_defaults(func=cmd_bible)

    for kind, help_txt in (
        ("add-character", "Add a character"),
        ("add-location", "Add a location"),
        ("add-prop", "Add a prop"),
    ):
        p_add = bible_sub.add_parser(kind, help=help_txt)
        p_add.add_argument("slug")
        p_add.add_argument("--id", required=True)
        p_add.add_argument("--name", required=True)
        p_add.add_argument("--description", default="")
        p_add.set_defaults(func=cmd_bible)

    p_attach = bible_sub.add_parser("attach-ref", help="Attach a reference_image to an entity")
    p_attach.add_argument("slug")
    p_attach.add_argument("--entity", required=True, choices=["character", "location", "prop"])
    p_attach.add_argument("--id", required=True, help="Entity id")
    p_attach.add_argument("--ref", required=True, help="reference_images.ref_id")
    p_attach.set_defaults(func=cmd_bible)

    p_ap_asset = bible_sub.add_parser("approve-asset", help="Approve a reference asset")
    p_ap_asset.add_argument("slug")
    p_ap_asset.add_argument("--entity", required=True, choices=["character", "location", "prop"])
    p_ap_asset.add_argument("--id", required=True)
    p_ap_asset.add_argument("--asset", required=True)
    p_ap_asset.set_defaults(func=cmd_bible)

    p_ap_ent = bible_sub.add_parser("approve-entity", help="Mark an entity approved")
    p_ap_ent.add_argument("slug")
    p_ap_ent.add_argument("--entity", required=True, choices=["character", "location", "prop"])
    p_ap_ent.add_argument("--id", required=True)
    p_ap_ent.set_defaults(func=cmd_bible)

    p_link = bible_sub.add_parser("link-shot", help="Link a shot to bible entities")
    p_link.add_argument("slug")
    p_link.add_argument("--shot", required=True)
    p_link.add_argument("--character", action="append", default=[])
    p_link.add_argument("--location", default=None)
    p_link.add_argument("--prop", action="append", default=[])
    p_link.add_argument(
        "--replace",
        action="store_true",
        help="Replace character/prop lists instead of merging",
    )
    p_link.set_defaults(func=cmd_bible)

    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv(Path.cwd() / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
