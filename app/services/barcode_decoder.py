"""
Barcode Decoder Service.
Decodes barcodes from different retail stores to extract article code and weight.
"""

from typing import Optional, Tuple
from decimal import Decimal


class BarcodeDecoder:
    """Decodes barcodes from various retail stores to extract weight and article code"""

    @staticmethod
    def decode(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode barcode to extract article code and weight.

        Args:
            barcode: The barcode string to decode

        Returns:
            Tuple of (article_code, weight_in_kg, store_type)
            - article_code: The article identifier (integer)
            - weight_in_kg: Weight in kilograms (float)
            - store_type: The identified store type (string)
        """
        if not barcode:
            return None, None, "unknown"

        # Try each decoder in order
        # IMPORTANT: Check longer/more specific patterns first to avoid false matches
        decoders = [
            BarcodeDecoder._decode_smart_alternative,  # Check this before reliance_smart (both start with ]C1)
            BarcodeDecoder._decode_reliance_smart,
            BarcodeDecoder._decode_reliance_fresh,     # Check this before star_bazar (both start with 21)
            BarcodeDecoder._decode_star_bazar,
            BarcodeDecoder._decode_food_square,        # Check this before rapsap (both start with W, food_square is longer)
            BarcodeDecoder._decode_rapsap,
            BarcodeDecoder._decode_mrdpl,
        ]

        for decoder in decoders:
            article_code, weight, store_type = decoder(barcode)
            if article_code is not None:
                return article_code, weight, store_type

        # If no decoder matched, return the barcode as article code
        try:
            return int(barcode), None, "unknown"
        except ValueError:
            return None, None, "unknown"

    @staticmethod
    def _decode_reliance_smart(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode Reliance Smart barcode (Smart & Essentials).
        Format: ]C12... (no length limit)
        Config: Start Barcode: 8, End Barcode: 16 | Start Weight: 17, End Weight: 21
        Article Code: Positions 8-16 = 600022496
        Weight: Positions 17-21 = 01001 grams
        Pattern: Starts with ]C12 (4th character is '2')
        """
        # Reliance Smart starts with ]C12, Smart Alternative starts with ]C10
        if barcode.startswith("]C12") and len(barcode) >= 21:
            try:
                # Extract article code (positions 8-16: 0-based [7:16])
                article_code = int(barcode[7:16])

                # Extract weight (positions 17-21: 0-based [16:21]) in grams
                weight_grams = int(barcode[16:21])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "reliance_smart"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_smart_alternative(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode Smart Alternative barcode.
        Format: ]C10... (no length limit)
        Config: Start Barcode: 11, End Barcode: 19 | Start Weight: 20, End Weight: 24
        Article Code: Positions 11-19 = 600022536
        Weight: Positions 20-24 = 02501 grams
        Pattern: Starts with ]C10 (4th character is '0')
        """
        # Smart Alternative starts with ]C10, Reliance Smart starts with ]C12
        if barcode.startswith("]C10") and len(barcode) >= 24:
            try:
                # Extract article code (positions 11-19: 0-based [10:19])
                article_code = int(barcode[10:19])

                # Extract weight (positions 20-24: 0-based [19:24]) in grams
                weight_grams = int(barcode[19:24])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "smart_alternative"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_reliance_fresh(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode Reliance Fresh barcode (FP & Signature).
        Format: 2110000600647840002021
        Config: Start Barcode: 8, End Barcode: 16 | Start Weight: 17, End Weight: 21
        Article Code: Positions 8-16 = 600647840
        Weight: Positions 17-21 = 02021 grams
        """
        if barcode.startswith("21") and len(barcode) >= 21:
            try:
                # Extract article code (positions 8-16: 0-based [7:16])
                article_code = int(barcode[7:16])

                # Extract weight (positions 17-21: 0-based [16:21]) in grams
                weight_grams = int(barcode[16:21])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "reliance_fresh"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_star_bazar(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode Star Bazar barcode.
        Format: 21452008000000100123
        Config: Start Barcode: 3, End Barcode: 6 | Start Weight: 13, End Weight: 17
        Article Code: Positions 3-6 = 4520
        Weight: Positions 13-17 = 00101 grams
        """
        if barcode.startswith("21") and len(barcode) >= 17:
            try:
                # Extract article code (positions 3-6: 0-based [2:6])
                article_code = int(barcode[2:6])

                # Extract weight (positions 13-17: 0-based [12:17]) in grams
                weight_grams = int(barcode[12:17])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "star_bazar"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_food_square(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode Food Square barcode.
        Format: W902979200110 (typically 13+ characters)
        Config: Start Barcode: 2, End Barcode: 8 | Start Weight: 9, End Weight: 13
        Article Code: Positions 2-8 = 9029792
        Weight: Positions 9-13 = 00110 grams
        """
        # Minimum length check to ensure we can extract required positions
        if barcode.startswith("W") and len(barcode) >= 13:
            try:
                # Extract article code (positions 2-8: 0-based [1:8])
                article_code = int(barcode[1:8])

                # Extract weight (positions 9-13: 0-based [8:13]) in grams
                weight_grams = int(barcode[8:13])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "food_square"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_rapsap(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode RAPSAP barcode.
        Format: W01930101000 (typically 12 characters, but can accept longer)
        Config: Start Barcode: 3, End Barcode: 7 | Start Weight: 8, End Weight: 12
        Article Code: Positions 3-7 = 01930
        Weight: Positions 8-12 = 01000 grams
        """
        # Accept 12-character barcodes (checked after Food Square which is 13+)
        if barcode.startswith("W") and len(barcode) == 12:
            try:
                # Extract article code (positions 3-7: 0-based [2:7])
                article_code = int(barcode[2:7])

                # Extract weight (positions 8-12: 0-based [7:12]) in grams
                weight_grams = int(barcode[7:12])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "rapsap"
            except (ValueError, IndexError):
                pass
        return None, None, ""

    @staticmethod
    def _decode_mrdpl(barcode: str) -> Tuple[Optional[int], Optional[float], str]:
        """
        Decode MRDPL barcode (Magson).
        Format: H10003000260
        Config: Start Barcode: 2, End Barcode: 6 | Start Weight: 7, End Weight: 12
        Article Code: Positions 2-6 = 10003
        Weight: Positions 7-12 = 000260 grams
        """
        if barcode.startswith("H") and len(barcode) >= 12:
            try:
                # Extract article code (positions 2-6: 0-based [1:6])
                article_code = int(barcode[1:6])

                # Extract weight (positions 7-12: 0-based [6:12]) in grams
                weight_grams = int(barcode[6:12])
                weight_kg = weight_grams / 1000.0

                return article_code, weight_kg, "mrdpl"
            except (ValueError, IndexError):
                pass
        return None, None, ""


def decode_barcode(barcode: str) -> dict:
    """
    Convenience function to decode barcode and return result as dictionary.

    Args:
        barcode: The barcode string to decode

    Returns:
        Dictionary with article_code, weight, and store_type
    """
    article_code, weight, store_type = BarcodeDecoder.decode(barcode)

    return {
        "article_code": article_code,
        "weight": weight,
        "store_type": store_type
    }
