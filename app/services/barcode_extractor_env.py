"""
Barcode Extractor Service using AWS Textract.
Extracts barcode numbers from images using OCR.
"""

import re
import os
import io
import base64
from typing import Optional, Dict, Any
import numpy as np
import cv2
from PIL import Image


class BarcodeExtractor:
    """
    Extracts barcode text from images using AWS Textract OCR.
    """

    def __init__(self, image_array: Optional[np.ndarray] = None, image_path: Optional[str] = None):
        """
        Initialize the BarcodeExtractor.

        Args:
            image_array: OpenCV BGR image array (numpy ndarray)
            image_path: Path to image file (alternative to image_array)
        """
        self.image_array = image_array
        self.image_path = image_path

        # Initialize AWS Textract client
        try:
            import boto3
            self.textract_client = boto3.client(
                'textract',
                region_name=os.getenv('AWS_REGION', 'us-east-1'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            print(f"Warning: Failed to initialize AWS Textract client: {e}")
            self.textract_client = None

    def _image_to_bytes(self) -> bytes:
        """
        Convert image to bytes for Textract processing.

        Returns:
            Image bytes in PNG format
        """
        if self.image_array is not None:
            # Convert BGR to RGB for PIL
            rgb_image = cv2.cvtColor(self.image_array, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
        elif self.image_path is not None:
            pil_image = Image.open(self.image_path)
        else:
            raise ValueError("No image provided")

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.read()

    def send_full_image_to_textract(self, use_analyze_document: bool = False) -> Dict[str, Any]:
        """
        Send the full image to AWS Textract for OCR processing.

        Args:
            use_analyze_document: If True, use AnalyzeDocument API; otherwise use DetectDocumentText

        Returns:
            Dictionary with extracted text data including lines and words
        """
        if not self.textract_client:
            return {"lines": [], "words": []}

        try:
            image_bytes = self._image_to_bytes()

            if use_analyze_document:
                response = self.textract_client.analyze_document(
                    Document={'Bytes': image_bytes},
                    FeatureTypes=['TABLES', 'FORMS']
                )
            else:
                response = self.textract_client.detect_document_text(
                    Document={'Bytes': image_bytes}
                )

            # Extract lines and words
            lines = []
            words = []

            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    lines.append({
                        'text': block.get('Text', ''),
                        'confidence': block.get('Confidence', 0)
                    })
                elif block['BlockType'] == 'WORD':
                    words.append({
                        'text': block.get('Text', ''),
                        'confidence': block.get('Confidence', 0)
                    })

            return {
                'lines': lines,
                'words': words,
                'raw_response': response
            }

        except Exception as e:
            print(f"Error in Textract OCR: {e}")
            return {"lines": [], "words": []}

    def extract_barcode_number_via_textract(self, use_analyze_document: bool = False) -> Optional[str]:
        """
        Extract barcode number from image using Textract OCR with improved digit extraction.

        Args:
            use_analyze_document: If True, use AnalyzeDocument API; otherwise use DetectDocumentText

        Returns:
            Extracted barcode string or None if not found
        """
        result = self.send_full_image_to_textract(use_analyze_document=use_analyze_document)

        if not result or (not result.get("lines") and not result.get("words")):
            print("⚠️ Textract returned no text")
            return None

        # Collect all text from lines and words
        texts = []
        for line in result.get("lines", []):
            text = (line.get("text") or "").strip()
            if text:
                texts.append(text)

        if not texts:
            for word in result.get("words", []):
                text = (word.get("text") or "").strip()
                if text:
                    texts.append(text)

        if not texts:
            print("⚠️ No text extracted from Textract response")
            return None

        # Join all text
        joined = "\n".join(texts)
        print(f"📝 Textract extracted text:\n{joined}")

        # Try to find barcode patterns
        candidates = []

        # 1) Direct long digit runs (common printed barcode numbers)
        candidates += re.findall(r"\b\d{10,22}\b", joined)

        # 2) Spaced/hyphenated digit runs: "2110 0000 0225 9700 181"
        spaced_runs = re.findall(r"(?:\d[\s-]?){10,30}", joined)
        for s in spaced_runs:
            cleaned = re.sub(r"[\s-]", "", s)
            if cleaned.isdigit() and 10 <= len(cleaned) <= 22:
                candidates.append(cleaned)

        # 3) Special patterns like ]C10, ]C12, W, H prefixes
        special_patterns = [
            r"]C1[02]\d{10,20}",  # ]C10 or ]C12 followed by digits
            r"W\d{11,13}",         # W followed by 11-13 digits
            r"H\d{10,12}",         # H followed by 10-12 digits
        ]
        for pattern in special_patterns:
            matches = re.findall(pattern, joined)
            candidates += matches

        if not candidates:
            print("⚠️ No barcode patterns found in Textract output")
            return None

        # Prefer longest candidate; break ties by frequency
        candidates_sorted = sorted(candidates, key=lambda x: (len(x), candidates.count(x)), reverse=True)
        barcode = candidates_sorted[0]

        print(f"✅ Textract extracted barcode: {barcode}")
        return barcode


def extract_barcode_from_image(image_array: np.ndarray, use_textract: bool = True) -> Optional[str]:
    """
    Convenience function to extract barcode from image array.

    Args:
        image_array: OpenCV BGR image array
        use_textract: Whether to use AWS Textract (True) or fallback methods (False)

    Returns:
        Extracted barcode string or None
    """
    if use_textract:
        extractor = BarcodeExtractor(image_array=image_array)
        return extractor.extract_barcode_number_via_textract()
    return None
