"""Image generation provider adapters (mock / dry-run / A1111 / Comfy probe)."""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


DEFAULT_A1111_URL = "http://127.0.0.1:7860"
DEFAULT_COMFY_URL = "http://127.0.0.1:8188"


@dataclass
class ImageGenRequest:
    prompt: str
    negative_prompt: str
    dest_path: Path
    reference_paths: list[Path] = field(default_factory=list)
    seed: Optional[int] = None
    settings: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False


@dataclass
class ImageGenResult:
    status: str  # completed | failed | dry_run | unavailable
    message: str
    output_path: Optional[Path] = None
    model_id: str = ""
    model_version: str = ""
    model_licence: str = ""
    seed: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)


class ImageGenProvider(ABC):
    name: str

    @abstractmethod
    def probe(self) -> tuple[bool, str]:
        """Return (available, message). Never downloads models."""

    @abstractmethod
    def generate(self, req: ImageGenRequest) -> ImageGenResult: ...


def write_placeholder_png(path: Path, rgb: tuple[int, int, int] = (48, 96, 144)) -> None:
    """Tiny local PNG for mock/tests — no model weights."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if cv2 is None:
        # Minimal 1x1 PNG
        path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )
        return
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    # OpenCV is BGR
    img[:] = (rgb[2], rgb[1], rgb[0])
    cv2.imwrite(str(path), img)


class DryRunProvider(ImageGenProvider):
    name = "dry-run"

    def probe(self) -> tuple[bool, str]:
        return True, "dry-run always available (no pixels written)"

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        return ImageGenResult(
            status="dry_run",
            message=f"Dry-run only; would write {req.dest_path}",
            output_path=None,
            model_id="dry-run",
            model_licence="n/a",
            seed=req.seed,
            meta={"prompt_chars": len(req.prompt), "refs": len(req.reference_paths)},
        )


class MockProvider(ImageGenProvider):
    name = "mock"

    def probe(self) -> tuple[bool, str]:
        return True, "mock placeholder PNG writer (no models)"

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        if req.dry_run:
            return DryRunProvider().generate(req)
        write_placeholder_png(req.dest_path)
        return ImageGenResult(
            status="completed",
            message=f"Mock candidate written to {req.dest_path}",
            output_path=req.dest_path,
            model_id="mock-placeholder",
            model_version="1",
            model_licence="n/a",
            seed=req.seed if req.seed is not None else 0,
            meta={"refs": [str(p) for p in req.reference_paths]},
        )


class ManualProvider(ImageGenProvider):
    name = "manual"

    def probe(self) -> tuple[bool, str]:
        return True, "manual: job records dest path for human fill-in"

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        if req.dry_run:
            return DryRunProvider().generate(req)
        req.dest_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar = req.dest_path.with_suffix(req.dest_path.suffix + ".manual.txt")
        sidecar.write_text(
            f"MANUAL IMAGE GEN\nprompt:\n{req.prompt}\n\nnegative:\n{req.negative_prompt}\n"
            f"dest: {req.dest_path}\nrefs:\n"
            + "\n".join(str(p) for p in req.reference_paths),
            encoding="utf-8",
        )
        return ImageGenResult(
            status="completed",
            message=f"Manual instructions at {sidecar}; place image at {req.dest_path}",
            output_path=req.dest_path,
            model_id="manual",
            model_licence="n/a",
            seed=req.seed,
            meta={"sidecar": str(sidecar), "awaiting_file": not req.dest_path.is_file()},
        )


class A1111Provider(ImageGenProvider):
    """Automatic1111 WebUI — only called when probe succeeds (no model downloads)."""

    name = "local"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("LOCAL_SD_URL", DEFAULT_A1111_URL)).rstrip("/")

    def probe(self) -> tuple[bool, str]:
        try:
            resp = requests.get(f"{self.base_url}/sdapi/v1/sd-models", timeout=2.0)
            resp.raise_for_status()
            models = resp.json()
            count = len(models) if isinstance(models, list) else 0
            return True, f"A1111 reachable at {self.base_url} ({count} model entries reported)"
        except requests.RequestException as e:
            return False, f"A1111 not reachable at {self.base_url}: {e}"

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        if req.dry_run:
            return DryRunProvider().generate(req)
        ok, msg = self.probe()
        if not ok:
            return ImageGenResult(status="unavailable", message=msg, model_id="a1111")

        payload: dict[str, Any] = {
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "steps": int(req.settings.get("steps", 20)),
            "width": int(req.settings.get("width", 512)),
            "height": int(req.settings.get("height", 512)),
        }
        if req.seed is not None:
            payload["seed"] = int(req.seed)

        try:
            if req.reference_paths:
                init = req.reference_paths[0]
                image_b64 = base64.b64encode(init.read_bytes()).decode("ascii")
                payload["init_images"] = [image_b64]
                payload["denoising_strength"] = float(req.settings.get("denoising_strength", 0.55))
                resp = requests.post(
                    f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=180
                )
            else:
                resp = requests.post(
                    f"{self.base_url}/sdapi/v1/txt2img", json=payload, timeout=180
                )
            resp.raise_for_status()
        except requests.RequestException as e:
            return ImageGenResult(
                status="failed",
                message=f"A1111 request failed: {e}",
                model_id="a1111",
                model_licence="depends-on-checkpoint",
            )

        images = resp.json().get("images") or []
        if not images:
            return ImageGenResult(
                status="failed",
                message="A1111 returned no images",
                model_id="a1111",
                model_licence="depends-on-checkpoint",
            )
        req.dest_path.parent.mkdir(parents=True, exist_ok=True)
        req.dest_path.write_bytes(base64.b64decode(images[0]))
        return ImageGenResult(
            status="completed",
            message=f"A1111 wrote {req.dest_path}",
            output_path=req.dest_path,
            model_id="a1111-local",
            model_licence="depends-on-checkpoint",
            seed=req.seed,
        )


class ComfyProvider(ImageGenProvider):
    """ComfyUI probe + stub. No workflow run without a local server + licensed graph."""

    name = "comfy"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("COMFY_URL", DEFAULT_COMFY_URL)).rstrip("/")

    def probe(self) -> tuple[bool, str]:
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=2.0)
            resp.raise_for_status()
            return True, f"ComfyUI reachable at {self.base_url}"
        except requests.RequestException as e:
            return False, (
                f"ComfyUI not reachable at {self.base_url}: {e}. "
                "Comfy Desktop Cloud-only installs are not used; no model downloads."
            )

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        if req.dry_run:
            return DryRunProvider().generate(req)
        ok, msg = self.probe()
        if not ok:
            return ImageGenResult(
                status="unavailable",
                message=msg,
                model_id="comfy",
                model_licence="adapter-gpl-3.0; checkpoint-separate",
            )
        return ImageGenResult(
            status="unavailable",
            message=(
                f"{msg}. Continuum will not submit a Comfy workflow until a licensed "
                "local graph + checkpoint are registered (model_registry.models)."
            ),
            model_id="comfy",
            model_licence="adapter-gpl-3.0; checkpoint-separate",
            meta={"server_up": True, "workflow_configured": False},
        )


_PROVIDERS: dict[str, type[ImageGenProvider]] = {
    "dry-run": DryRunProvider,
    "mock": MockProvider,
    "manual": ManualProvider,
    "local": A1111Provider,
    "comfy": ComfyProvider,
}


def get_provider(name: str) -> ImageGenProvider:
    key = name.strip().lower()
    if key not in _PROVIDERS:
        raise ValueError(
            f"Unknown image gen provider '{name}'. Choices: {', '.join(sorted(_PROVIDERS))}"
        )
    return _PROVIDERS[key]()


def list_providers() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in sorted(_PROVIDERS):
        provider = _PROVIDERS[name]()
        ok, message = provider.probe()
        rows.append({"name": name, "available": ok, "message": message})
    return rows


def probe_provider(name: str) -> tuple[bool, str]:
    return get_provider(name).probe()
