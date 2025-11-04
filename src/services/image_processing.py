# src/services/image_processing.py
from __future__ import annotations

import io
from typing import Tuple, TypedDict

from PIL import Image, ImageOps, UnidentifiedImageError

# Guard against decompression bombs
Image.MAX_IMAGE_PIXELS = 100_000_000


class ImageProcessingError(Exception):
    pass


class InvalidImageError(ImageProcessingError):
    pass


class ImageTooLargeError(ImageProcessingError):
    pass


class ImageMetadata(TypedDict):
    width: int
    height: int
    format: str


def process_image_to_jpeg_fill_center(
    img_bytes: bytes,
    target_size: Tuple[int, int] = (1024, 1024),
    quality: int = 85,
    background_rgb: Tuple[int, int, int] = (255, 255, 255),
    progressive: bool = True,
    optimize: bool = True,
) -> Tuple[bytes, ImageMetadata]:
    """
    Process an image to JPEG format with specific requirements.

    Load an image from bytes, normalize orientation, handle transparency
    Scale-to-fill with center crop, and return JPEG bytes along with metadata.

    Metadata includes mandatory: 'width', 'height', 'format'.
    Additional keys can be added in the future by extending ImageMetadata.
    """
    try:
        with Image.open(io.BytesIO(img_bytes)) as pil_img:
            img = ImageOps.exif_transpose(pil_img)
            if img is None:
                raise ImageProcessingError("EXIF transpose failed")

            # Convert to RGB with white background if needed
            if img.mode in ("RGBA", "LA", "P"):
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg = Image.new("RGB", img.size, background_rgb)
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Scale to fill and center-crop
            img = ImageOps.fit(
                img,
                target_size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

            # Extract metadata from the final image
            metadata: ImageMetadata = {
                "width": img.width,
                "height": img.height,
                "format": "JPEG",  # Fixed as we're saving to JPEG
            }

            out = io.BytesIO()
            img.save(
                out,
                format=metadata["format"],
                quality=quality,
                optimize=optimize,
                progressive=progressive,
            )
            processed_bytes = out.getvalue()

            return processed_bytes, metadata

    except UnidentifiedImageError as e:
        raise InvalidImageError("Invalid image file") from e
    except Image.DecompressionBombError as e:
        raise ImageTooLargeError("Image resolution too large") from e
    except Exception as e:
        raise ImageProcessingError(str(e)) from e
