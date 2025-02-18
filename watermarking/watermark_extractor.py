import hashlib
from copy import deepcopy
from typing import Union, Tuple, Optional, List
from dataclasses import dataclass
import numpy as np
from PIL import Image
from pydicom import dcmread
from blockchain.blockchain import Blockchain
from utils.utils import (
    generate_random_binary_array_from_string,
    compute_ber,
    reshape_and_compute
)
from watermarking.utils import compute_hash, hex_to_binary_array


@dataclass
class ExtractionResult:
    """Data class to hold extraction results"""
    watermark: np.ndarray
    ber: float
    original_watermark: np.ndarray
    is_match: bool


class WatermarkExtractor:
    def __init__(self, config):
        self.config = config
        self.blockchain = Blockchain(config.blockchain_path)

    def _load_image(self) -> np.ndarray:
        """Load image based on data type."""
        if self.config.data_type == "dcm":
            return dcmread(self.config.data_path).pixel_array
        return np.array(Image.open(self.config.data_path).convert('L'))

    def _extract_watermark_from_image(
            self,
            image: np.ndarray,
            transaction: dict
    ):
        """Extract watermark from image using given parameters."""
        # Setup parameters
        kernel = np.array(transaction["kernel"])
        stride = transaction["stride"]
        t_hi = transaction["t_hi"]
        max_pixel_value = 2 ** transaction["bit_depth"]

        # Initialize arrays
        recovered_image = deepcopy(image)
        extracted_bits = []
        extracted_bits_256 = np.zeros((256, 2)).astype(np.float64)
        pos_wat = 0
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
        idx_secret_key = 0
        # Extraction loop
        for y in range(out_height):
            for x in range(out_width):
                if secret_positions[idx_secret_key] == 0:
                    idx_secret_key +=1
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
                    idx_secret_key += 1
                    continue

                if center == max_pixel_value - 1:
                    overflow_positions.append((y_center, x_center))
                    idx_secret_key += 1
                    continue

                # Extract bit and update image
                error, bit = self._extraction_value(error_w, t_hi)
                if bit in (0, 1):
                    extracted_bits.append(bit)
                    extracted_bits_256[idx_secret_key%256][0] += bit
                    extracted_bits_256[idx_secret_key%256][1] += 1
                    if y< 1:
                        print("ext pos", y, x, bit)
                idx_secret_key += 1
                recovered_image[y_center, x_center] = neighbors + error

        if not overflow_positions:
            return np.array(extracted_bits), np.array(extracted_bits_256)
        else:
            return np.array(extracted_bits[:-len(overflow_positions) - 1]), np.array(extracted_bits_256)

    @staticmethod
    def _extraction_value(error_w: int, thresh_hi: int) -> Tuple[int, Optional[int]]:
        """Calculate extraction value and bit."""
        if error_w > (2 * thresh_hi + 1):
            return error_w - thresh_hi - 1, None
        return (error_w - error_w % 2) // 2, error_w % 2

    def extract(self) -> dict:
        """Main extraction method."""
        # Load and hash image
        image = self._load_image()
        image_hash = compute_hash(image)
        ber = 1
        # Get transaction from blockchain
        history, transaction = self.blockchain.get_transaction_history(image_hash)
        if not transaction:
            print("No matching image hash found in blockchain")
            blocks = self.blockchain.blocks
            for _, block in blocks.items():
                if block.info == "embedder":
                    for _, transaction_current in block.transaction["transaction_dict"].items():
                        if transaction_current["data_type"] == self.config.data_type:
                            extracted_watermark, extracted_watermark_256 = self._extract_watermark_from_image(image, transaction_current)

                            original_watermark = hex_to_binary_array(transaction_current["watermark"])
                            extracted_watermark = reshape_and_compute(extracted_watermark)
                            # print("ext wat", [int(i/j>0.5) for i, j in extracted_watermark_256])
                            # print("original wat", original_watermark)
                            extracted_watermark_256 = np.array([int(i/j>0.5) for i, j in extracted_watermark_256])

                            ber = compute_ber(extracted_watermark_256, original_watermark)
                            if ber < 0.4:
                                history = {
                                    'ber': ber,
                                    'block_number': block.header.block_number,
                                    'block_hash': block.hash,
                                    'timestamp': block.header.timestamp,
                                    'info': block.info,
                                    'image_hash': transaction_current['hash_image_wat']
                                }
                                return history

            history = {
                'ber': 0.5,
                'block_number': None,
                'block_hash': None,
                'timestamp': None,
                'info': "Image doesnt belong to Paroma",
                'image_hash': None

            }
            return history

        else:
            print("A matching image hash found in blockchain")
            history["ber"] = 0

        return history