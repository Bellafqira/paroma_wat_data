import hashlib
import secrets
from copy import deepcopy
from typing import Dict, Tuple, Union
import numpy as np
from PIL import Image
from datetime import datetime
from dataclasses import dataclass

from pydicom import dcmread

from watermarking.utils import string_to_sha256_bits, generate_secret_key, verify_secret_key, compute_hash, \
    generate_watermark


@dataclass
class EmbedderTransaction:
    """Data class for watermark transaction information"""
    timestamp: str
    secret_key: str
    message: str
    watermark: str
    kernel: list
    stride: int
    t_hi: float
    hash_image_wat: str
    hash_image_orig: str
    bit_depth: int
    data_type: str
    operation_type: str


class WatermarkEmbedder:
    def __init__(self, config):
        self.config = config
        self.secret_key, self.key_length = generate_secret_key()  # Generate secure key
        self.bit_depth = config.bit_depth  # Default 8-bit image
        self.max_pixel_value = 2 ** self.bit_depth

    def _generate_secret_positions(self, size: int) -> np.ndarray:
        """Generate secret positions from the secret key."""
        from utils.utils import generate_random_binary_array_from_string
        # Convert hex key to binary string for position generation
        return generate_random_binary_array_from_string(self.secret_key, size)

    @staticmethod
    def _embedding_value(error: int, thresh_hi: int, bit: int) -> Tuple[Union[int, None], Union[int, None]]:
        """Calculate embedding value based on error and threshold."""
        if error > thresh_hi:
            return error + thresh_hi + 1, None
        elif 0 <= error <= thresh_hi:
            return 2 * error + bit, bit
        else:
            raise ValueError("Invalid error value for embedding")

    def _handle_overflow(self, image_np: np.ndarray, original_image: np.ndarray,
                         overflow_array: list, secret_positions: np.ndarray,
                         kernel: np.ndarray, stride: int, idx_secret_key: int) -> np.ndarray:
        """Handle overflow cases during watermark embedding."""
        if not overflow_array:
            return image_np

        image_height, image_width = image_np.shape
        kernel_height, kernel_width = kernel.shape
        output_height = (image_height - kernel_height) // stride + 1
        output_width = (image_width - kernel_width) // stride + 1

        # idx_overflow = len(overflow_array) - 1
        # idx_secret_key = len(secret_positions) - 1

        #  Perform the embedding starting by the last regions
        if len(overflow_array) != 0:
            idx_overflow = len(overflow_array)
            for y in range(output_height - 1, -1, -1):
                for x in range(output_width - 1, -1, -1):
                    if idx_overflow == -1:
                        break

                    if secret_positions[idx_secret_key-1] == 1:
                        region = original_image[y * stride:y * stride + kernel_height,
                                 x * stride:x * stride + kernel_width]
                        neighbours = np.sum(region * kernel) // 1
                        center = original_image[y * stride + kernel_height // 2,
                                                x * stride + kernel_width // 2]

                        error = center - neighbours
                        if error >= 0:
                            if center in (self.max_pixel_value - 1, self.max_pixel_value - 2):
                                idx_secret_key -= 1
                                continue

                            error_w, bit = self._embedding_value(error, self.config.t_hi,
                                                                 overflow_array[idx_overflow-1])
                            if error_w is not None:
                                image_np[y * stride + kernel_height // 2,
                                         x * stride + kernel_width // 2] = neighbours + error_w
                            if bit in (0, 1):
                                idx_overflow -= 1

                    idx_secret_key -= 1

        return image_np

    def embed_watermarks(self) -> EmbedderTransaction:
        """Main method to embed watermarks in the image."""
        # Verify secret key
        if not verify_secret_key(self.secret_key):
            raise ValueError("Invalid secret key generated")

        if self.config.data_type == "dcm":
            ds = dcmread(self.config.data_path)
            image_np = ds.pixel_array
        else:
            # Load and prepare image
            image = Image.open(self.config.data_path).convert('L')
            image_np = np.array(image)

        original_image = deepcopy(image_np)
        # Prepare parameters
        kernel = np.array(self.config.kernel)
        watermark = generate_watermark(self.config.message, self.secret_key)
        timestamp = str(datetime.now().timestamp())

        # Generate secret positions using the 256-bit key
        image_size = image_np.size
        secret_positions = self._generate_secret_positions(image_size)

        # Calculate dimensions
        image_height, image_width = image_np.shape
        kernel_height, kernel_width = kernel.shape
        output_height = (image_height - kernel_height) // self.config.stride + 1
        output_width = (image_width - kernel_width) // self.config.stride + 1

        idx_wat = 0
        idx_secret_key = 0
        overflow_array = []

        # Main embedding loop
        print("Starting watermark embedding process...")
        for y in range(output_height):
            for x in range(output_width):
                if secret_positions[idx_secret_key] == 1:
                    region = image_np[y * self.config.stride:y * self.config.stride + kernel_height,
                             x * self.config.stride:x * self.config.stride + kernel_width]
                    neighbours = np.sum(region * kernel) // 1
                    center_y = y * self.config.stride + kernel_height // 2
                    center_x = x * self.config.stride + kernel_width // 2
                    center = image_np[center_y, center_x]

                    error = center - neighbours
                    if error >= 0:
                        if center == (self.max_pixel_value - 2):
                            image_np[center_y, center_x] += 1
                            overflow_array.append(1)
                            idx_secret_key += 1
                            idx_wat += 1
                            continue
                        elif center == (self.max_pixel_value - 1):
                            overflow_array.append(0)
                            idx_secret_key += 1
                            idx_wat += 1
                            continue

                        error_w, bit = self._embedding_value(error, self.config.t_hi, watermark[idx_wat % 256])

                        if error_w is not None:
                            image_np[center_y, center_x] = neighbours + error_w

                            if bit in (0, 1) and y<1:
                                print("pos embed =", y, x, bit)
                                # idx_wat += 1

                idx_secret_key += 1
                idx_wat += 1

        print(f"Initial embedding complete. Handling {len(overflow_array)} overflow cases...")
        # Handle overflow cases
        image_np = self._handle_overflow(image_np, original_image, overflow_array,
                                         secret_positions, kernel, self.config.stride, idx_secret_key)

        # Create and save watermarked image
        if self.config.data_type == "dcm":
            ds.PixelData = image_np.tobytes()
            ds.save_as(self.config.save_path)
        else:
            # Load and prepare image
            watermarked_image = Image.fromarray(np.uint8(image_np))
            watermarked_image.save(self.config.save_path)

        # Generate final watermark hash
        final_watermark = str(hashlib.sha256(
            (self.config.message + self.secret_key).encode()
        ).hexdigest())

        # final_watermark = ''.join(format(byte, '08b') for byte in final_watermark)

        # Create transaction
        transaction = EmbedderTransaction(
            timestamp=timestamp,
            secret_key=self.secret_key,  # Now using the secure 256-bit key
            message=self.config.message,
            watermark=final_watermark,
            kernel=self.config.kernel,
            stride=self.config.stride,
            t_hi=self.config.t_hi,
            hash_image_wat=compute_hash(image_np),
            hash_image_orig=compute_hash(original_image),
            bit_depth=self.bit_depth,
            data_type=self.config.data_type,
            operation_type=self.config.operation_type
        )

        print(f"Watermark embedding completed successfully")
        return transaction