import hashlib
from copy import deepcopy
from typing import Union, Tuple, Dict, Optional
from dataclasses import dataclass
import numpy as np
from PIL import Image
from pydicom import dcmread
from datetime import datetime

from blockchain.blockchain import Blockchain
from utils.utils import generate_random_binary_array_from_string, compute_ber
from watermarking.utils import bits_to_hexdigest, hex_to_binary_array, compute_hash


@dataclass
class RemoveResult:
    """Data class for extraction results"""
    recovered_image: np.ndarray
    extracted_watermark: str
    original_watermark: np.ndarray
    ber: float
    transaction: Dict


@dataclass
class RemovalTransaction:
    """Data class for watermark removal transaction"""
    timestamp: str
    operation_type: str = "removal"
    original_image_hash: str = ""
    watermarked_image_hash: str = ""
    recovered_image_hash: str = ""
    extraction_ber: float = 0.5
    original_watermark: str = ""
    extracted_watermark: str = ""
    removal_parameters: Dict = None


class WatermarkRemove:
    def __init__(self, config):
        self.config = config
        self.blockchain = Blockchain(config.blockchain_path)

    def _load_image(self) -> Tuple[np.ndarray, Optional[dcmread]]:
        """Load image and return array and DICOM dataset if applicable."""
        if self.config.data_type == "dcm":
            ds = dcmread(self.config.data_path)
            return np.array(ds.pixel_array), ds
        image = Image.open(self.config.data_path).convert('L')
        return np.array(image), None

    def _extract_watermark(self, image: np.ndarray, transaction: Dict) -> Tuple[np.ndarray, np.ndarray, list]:
        """Extract watermark from image using transaction parameters."""
        # Setup parameters
        kernel = np.array(transaction["kernel"])
        stride = transaction["stride"]
        t_hi = transaction["t_hi"]
        max_pixel_value = 2 ** transaction["bit_depth"]

        # Initialize arrays
        recovered_image = deepcopy(image)
        extracted_bits = []
        overflow_positions = []

        # Generate secret positions
        image_size = image.size
        secret_positions = generate_random_binary_array_from_string(
            transaction["secret_key"],
            image_size
        )

        # Calculate dimensions
        height, width = image.shape
        k_height, k_width = kernel.shape
        out_height = (height - k_height) // stride + 1
        out_width = (width - k_width) // stride + 1

        # Extraction loop
        for y in range(out_height):
            for x in range(out_width):
                if not secret_positions[y * out_width + x]:
                    continue

                # Get region coordinates
                y_start = y * stride
                x_start = x * stride
                y_center = y_start + k_height // 2
                x_center = x_start + k_width // 2

                # Extract region and calculate values
                region = recovered_image[y_start:y_start + k_height,
                         x_start:x_start + k_width]
                neighbors = np.sum(region * kernel) // 1
                center = recovered_image[y_center, x_center]

                error_w = center - neighbors
                if error_w < 0:
                    continue

                if center == max_pixel_value - 1:
                    overflow_positions.append((y_center, x_center))
                    continue

                # Extract bit and update image
                error, bit = self._extraction_value(error_w, t_hi)
                if bit in (0, 1):
                    extracted_bits.append(bit)

                recovered_image[y_center, x_center] = neighbors + error

        return recovered_image, np.array(extracted_bits), overflow_positions

    @staticmethod
    def _extraction_value(error_w: int, thresh_hi: int) -> Tuple[int, Optional[int]]:
        """Calculate extraction value and bit."""
        if error_w > (2 * thresh_hi + 1):
            return error_w - thresh_hi - 1, None
        bit = error_w % 2
        return (error_w - bit) // 2, bit

    @staticmethod
    def _handle_overflow(recovered_image: np.ndarray,
                         extracted_bits: np.ndarray,
                         overflow_positions: list) -> Tuple[np.ndarray, np.ndarray]:
        """Handle overflow positions in extraction."""
        if not overflow_positions:
            return recovered_image, extracted_bits

        overflow_wat = extracted_bits[-len(overflow_positions):]
        for idx, pos in enumerate(overflow_positions):
            recovered_image[pos] -= overflow_wat[idx]

        return recovered_image, extracted_bits[:-len(overflow_positions) - 1]

    def _save_results(self,
                      recovered_image: np.ndarray,
                      extracted_watermark: str,
                      dicom_ds: Optional[dcmread]) -> None:
        """Save recovered image and extracted watermark."""
        # Save extracted watermark
        np.save(self.config.ext_wat_path, extracted_watermark)

        # Save recovered image
        if dicom_ds is not None:
            dicom_ds.PixelData = recovered_image.tobytes()
            dicom_ds.save_as(self.config.save_path)
        else:
            Image.fromarray(np.uint8(recovered_image)).save(self.config.save_path)

    def extract_and_remove(self) -> RemoveResult:
        """Main method to extract watermark and recover original image."""
        # Load image
        image, dicom_ds = self._load_image()
        image_hash = compute_hash(image)
        # Get transaction from blockchain
        _, transaction = self.blockchain.get_transaction_history(image_hash)
        if not transaction:
            raise ValueError("No matching watermark found in blockchain")

        # Extract watermark and recover image
        recovered_image, extracted_bits, overflow_positions = self._extract_watermark(
            image, transaction
        )

        # Handle overflow
        recovered_image, extracted_watermark = self._handle_overflow(
            recovered_image, extracted_bits, overflow_positions
        )

        # Compare watermarks
        original_watermark = hex_to_binary_array(transaction["watermark"])

        original_watermark = np.tile(
            original_watermark,
            len(extracted_watermark) // len(original_watermark) + 1
        )[:len(extracted_watermark)]

        # Calculate BER
        ber = compute_ber(original_watermark, extracted_watermark)

        extracted_watermark = bits_to_hexdigest(extracted_watermark[:256])

        # Create removal transaction
        removal_transaction = RemovalTransaction(
            timestamp=str(datetime.now().timestamp()),
            original_image_hash=transaction.get("hash_image_orig", ""),
            watermarked_image_hash=image_hash,
            recovered_image_hash=compute_hash(recovered_image),
            extraction_ber=float(ber),
            original_watermark=transaction["watermark"],
            extracted_watermark=extracted_watermark,
            removal_parameters={
                "kernel": transaction["kernel"],
                "stride": transaction["stride"],
                "t_hi": transaction["t_hi"],
                "bit_depth": transaction["bit_depth"]
            }
        ).__dict__

        # Save results
        self._save_results(recovered_image, extracted_watermark, dicom_ds)

        print(f"Watermark extracted successfully (BER: {ber:.4f})")

        return RemoveResult(
            recovered_image=recovered_image,
            extracted_watermark=extracted_watermark,
            original_watermark=original_watermark,
            ber=ber,
            transaction=removal_transaction
        )

