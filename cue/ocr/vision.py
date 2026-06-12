from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class OCRError(RuntimeError):
    pass


@dataclass(frozen=True)
class LineItem:
    text: str
    mid_y: float
    min_x: float


def extract_structured_text(path: Path, *, automatically_detect_language: bool) -> str:
    import objc
    import Vision
    import Quartz
    from Foundation import NSURL

    image_path = Path(path).expanduser().resolve()
    if not image_path.exists():
        raise OCRError(f"Image not found: {image_path}")

    with objc.autorelease_pool():
        input_url = NSURL.fileURLWithPath_(str(image_path))
        input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)
        if input_image is None:
            raise OCRError(f"Could not decode image: {image_path}")

        observations: list = []
        error_holder: list[object] = []

        def handler(request, error) -> None:
            if error is not None:
                error_holder.append(error)
                return
            observations.extend(request.results() or [])

        request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
        configure_recognition(request, automatically_detect_language=automatically_detect_language)

        vision_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
            input_image,
            None,
        )
        success, perform_error = vision_handler.performRequests_error_([request], None)
        if perform_error is not None:
            raise OCRError(f"Vision OCR failed: {perform_error}")
        if not success:
            raise OCRError("Vision OCR request did not succeed.")
        if error_holder:
            raise OCRError(f"Vision OCR failed: {error_holder[0]}")

        return format_observations(observations)


def configure_recognition(request, *, automatically_detect_language: bool) -> None:
    import Vision

    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    if automatically_detect_language:
        request.setAutomaticallyDetectsLanguage_(True)
    else:
        request.setAutomaticallyDetectsLanguage_(False)
        request.setRecognitionLanguages_(["en-US"])


def format_observations(observations) -> str:
    items: list[LineItem] = []
    for observation in observations:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        candidate = candidates[0]
        box = observation.boundingBox()
        items.append(
            LineItem(
                text=str(candidate.string()),
                mid_y=float(box.origin.y + box.size.height / 2),
                min_x=float(box.origin.x),
            )
        )

    if not items:
        return ""

    sorted_items = sorted(
        items,
        key=lambda item: (-item.mid_y, item.min_x),
    )

    lines: list[list[LineItem]] = []
    line_threshold = 0.02

    for item in sorted_items:
        if lines and abs(item.mid_y - lines[-1][0].mid_y) <= line_threshold:
            lines[-1].append(item)
        else:
            lines.append([item])

    return "\n".join(
        " ".join(part.text for part in sorted(line, key=lambda part: part.min_x))
        for line in lines
    )
