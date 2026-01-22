import os
from typing import Any, Dict, List, Optional

import boto3
import cv2
from dotenv import load_dotenv

load_dotenv()


class BarcodeExtractor:
    def __init__(
        self,
        image_path: Optional[str] = None,
        image_array: Optional[Any] = None,
        aws_region: Optional[str] = None,
    ):
        """
        image_path: path to image (optional)
        image_array: OpenCV image (BGR or grayscale) (optional)
        aws_region: override AWS region (optional)
        """
        self.image_path = image_path
        self.image = image_array
        self.extracted_data: Dict[str, Any] = {}

        region = aws_region or os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

        # ✅ boto3 will resolve credentials automatically:
        # env vars, ~/.aws/credentials, IAM role (EC2/ECS/Lambda), etc.
        self.textract_client = boto3.client("textract", region_name=region)

        # Load image from path if not provided as array
        if self.image is None and self.image_path:
            self.image = cv2.imread(self.image_path)

        if self.image is None:
            raise ValueError("No valid image provided (image_path or image_array).")

    def _to_image_bytes(self, img, fmt: str = ".jpg") -> bytes:
        """
        Convert OpenCV image -> bytes for Textract.
        Use fmt='.png' for lossless.
        """
        ok, buffer = cv2.imencode(fmt, img)
        if not ok:
            raise ValueError("Failed to encode image to bytes.")
        return buffer.tobytes()

    def send_full_image_to_textract(
        self,
        use_analyze_document: bool = False,
        fmt: str = ".jpg",
        include_raw_response: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends FULL image to Textract.

        use_analyze_document=False -> detect_document_text (cheaper)
        use_analyze_document=True  -> analyze_document (FORMS/TABLES)
        """

        image_bytes = self._to_image_bytes(self.image, fmt=fmt)

        if use_analyze_document:
            response = self.textract_client.analyze_document(
                Document={"Bytes": image_bytes},
                FeatureTypes=["FORMS", "TABLES"],
            )
        else:
            response = self.textract_client.detect_document_text(
                Document={"Bytes": image_bytes}
            )

        lines: List[Dict[str, Any]] = []
        words: List[Dict[str, Any]] = []

        for block in response.get("Blocks", []):
            btype = block.get("BlockType")
            if btype == "LINE":
                lines.append(
                    {
                        "text": block.get("Text", ""),
                        "confidence": float(block.get("Confidence", 0.0)),
                        "bbox": block.get("Geometry", {}).get("BoundingBox", {}) or {},
                    }
                )
            elif btype == "WORD":
                words.append(
                    {
                        "text": block.get("Text", ""),
                        "confidence": float(block.get("Confidence", 0.0)),
                        "bbox": block.get("Geometry", {}).get("BoundingBox", {}) or {},
                    }
                )

        result: Dict[str, Any] = {"lines": lines, "words": words}

        if include_raw_response:
            result["raw_response"] = response

        self.extracted_data = result
        return result

    def extract_barcode_number_via_textract(
        self,
        use_analyze_document: bool = False,
        fmt: str = ".jpg",
    ) -> Optional[str]:
        """
        Extract barcode number from image using Textract.
        Returns the detected barcode number or None if not found.
        """
        result = self.send_full_image_to_textract(
            use_analyze_document=use_analyze_document,
            fmt=fmt,
            include_raw_response=False,
        )

        print("====== TEXTRACT DEBUG ======")
        print("LINES:", [l["text"] for l in result.get("lines", [])])
        print("WORDS:", [w["text"] for w in result.get("words", [])])
        print("============================")

        # TODO: Add barcode extraction logic here
        return None
