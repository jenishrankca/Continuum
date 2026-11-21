"""Empty-by-default model/adapter registry (board 20261121-15). No downloads."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

REGISTRY_FILENAME = "model_registry.yaml"
PACKAGE_REGISTRY = Path(__file__).resolve().parent / REGISTRY_FILENAME


@dataclass
class AdapterRecord:
    id: str
    kind: str
    provider: str = ""
    licence: str = ""
    local_path: Optional[str] = None
    endpoint_env: Optional[str] = None
    default_url: Optional[str] = None
    notes: str = ""


@dataclass
class ModelRecord:
    id: str
    version: str = ""
    licence: str = ""
    source_url: str = ""
    local_path: Optional[str] = None
    compatible_adapters: list[str] = field(default_factory=list)
    vram_notes: str = ""
    default: bool = False


@dataclass
class ModelRegistry:
    schema_version: int
    adapters: list[AdapterRecord] = field(default_factory=list)
    models: list[ModelRecord] = field(default_factory=list)
    path: Optional[Path] = None

    def get_adapter(self, adapter_id: str) -> Optional[AdapterRecord]:
        for a in self.adapters:
            if a.id == adapter_id or a.provider == adapter_id:
                return a
        return None

    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        for m in self.models:
            if m.id == model_id:
                return m
        return None


def _parse_adapter(raw: dict[str, Any]) -> AdapterRecord:
    return AdapterRecord(
        id=str(raw["id"]),
        kind=str(raw.get("kind", "image") or "image"),
        provider=str(raw.get("provider", raw.get("id", "")) or ""),
        licence=str(raw.get("licence", "") or ""),
        local_path=raw.get("local_path"),
        endpoint_env=raw.get("endpoint_env"),
        default_url=raw.get("default_url"),
        notes=str(raw.get("notes", "") or ""),
    )


def _parse_model(raw: dict[str, Any]) -> ModelRecord:
    return ModelRecord(
        id=str(raw["id"]),
        version=str(raw.get("version", "") or ""),
        licence=str(raw.get("licence", "") or ""),
        source_url=str(raw.get("source_url", "") or ""),
        local_path=raw.get("local_path"),
        compatible_adapters=list(raw.get("compatible_adapters") or []),
        vram_notes=str(raw.get("vram_notes", "") or ""),
        default=bool(raw.get("default", False)),
    )


def validate_registry(data: dict[str, Any]) -> list[str]:
    """Return validation error strings (empty = ok). Never downloads."""
    errors: list[str] = []
    if "schema_version" not in data:
        errors.append("missing schema_version")
    adapters = data.get("adapters")
    if adapters is None:
        errors.append("missing adapters list")
    elif not isinstance(adapters, list):
        errors.append("adapters must be a list")
    else:
        seen: set[str] = set()
        for i, raw in enumerate(adapters):
            if not isinstance(raw, dict):
                errors.append(f"adapters[{i}] must be a mapping")
                continue
            aid = raw.get("id")
            if not aid:
                errors.append(f"adapters[{i}] missing id")
            elif aid in seen:
                errors.append(f"duplicate adapter id '{aid}'")
            else:
                seen.add(str(aid))
            if not raw.get("kind"):
                errors.append(f"adapters[{aid or i}] missing kind")
    models = data.get("models")
    if models is None:
        errors.append("missing models list (use [] when empty)")
    elif not isinstance(models, list):
        errors.append("models must be a list")
    else:
        seen_m: set[str] = set()
        for i, raw in enumerate(models):
            if not isinstance(raw, dict):
                errors.append(f"models[{i}] must be a mapping")
                continue
            mid = raw.get("id")
            if not mid:
                errors.append(f"models[{i}] missing id")
            elif mid in seen_m:
                errors.append(f"duplicate model id '{mid}'")
            else:
                seen_m.add(str(mid))
            if raw.get("default") and not raw.get("licence"):
                errors.append(f"default model '{mid}' must declare licence")
    return errors


def load_registry(path: Path | None = None) -> ModelRegistry:
    target = path or PACKAGE_REGISTRY
    with open(target, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    errors = validate_registry(data)
    if errors:
        raise ValueError("Invalid model registry: " + "; ".join(errors))
    return ModelRegistry(
        schema_version=int(data.get("schema_version", 1)),
        adapters=[_parse_adapter(a) for a in data.get("adapters") or []],
        models=[_parse_model(m) for m in data.get("models") or []],
        path=target,
    )


def summarize_registry(registry: ModelRegistry) -> str:
    lines = [
        f"Model registry v{registry.schema_version} ({registry.path})",
        f"  adapters: {len(registry.adapters)}",
        f"  models:   {len(registry.models)} (empty means no bundled weights)",
    ]
    for a in registry.adapters:
        lines.append(
            f"  - adapter {a.id} kind={a.kind} provider={a.provider} "
            f"licence={a.licence or '(unset)'} path={a.local_path or '—'}"
        )
    for m in registry.models:
        lines.append(
            f"  - model {m.id}@{m.version or '?'} licence={m.licence or '(unset)'} "
            f"path={m.local_path or '—'}"
        )
    return "\n".join(lines)
