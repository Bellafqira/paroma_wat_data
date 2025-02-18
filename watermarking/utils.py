import secrets
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union, List
from PIL import Image
import numpy as np


def generate_secret_key(add_timestamp: bool = True) -> Tuple[str, int]:
    """
    Generate a secure 256-bit secret key and return it as a hexadecimal string.

    Args:
        add_timestamp: bool, whether to include timestamp in key generation

    Returns:
        Tuple containing:
            - str: The 256-bit secret key as a 64-character hexadecimal string
            - int: The length of the key in bits (always 256)
    """
    # Generate 32 bytes (256 bits) of random data
    random_bytes = secrets.token_bytes(32)

    if add_timestamp:
        # Add timestamp for additional uniqueness
        from datetime import datetime
        timestamp = datetime.now().timestamp()
        timestamp_bytes = str(timestamp).encode()

        # Combine random bytes with timestamp
        combined = random_bytes + timestamp_bytes

        # Hash the combined value to get final 256-bit key
        key = hashlib.sha256(combined).hexdigest()
    else:
        # Convert random bytes directly to hexadecimal
        key = random_bytes.hex()

    # Verify key length
    assert len(key) == 64, "Key length must be 64 hexadecimal characters (256 bits)"

    return key, 256


def verify_secret_key(key: str) -> bool:
    """
    Verify that a secret key is valid (256 bits represented as 64 hex characters).

    Args:
        key: str, the secret key to verify

    Returns:
        bool: True if key is valid, False otherwise
    """
    try:
        # Check length
        if len(key) != 64:
            return False

        # Check if string is valid hexadecimal
        int(key, 16)

        return True
    except ValueError:
        return False


def string_to_sha256_bits(input_string):
    """
    Hashes a string using SHA256 and returns a NumPy array of bits.

    Args:
        input_string: The string to hash.

    Returns:
        A NumPy array representing the SHA256 hash as bits.
    """
    sha256_hash = hashlib.sha256(input_string.encode('utf-8')).hexdigest()
    # bits = hex_to_binary_array(sha256_hash)
    #
    # # for char in sha256_hash:
    # #     hex_value = int(char, 16)
    # #     bits.extend([int(bit) for bit in bin(hex_value)[2:].zfill(4)])  # Convert hex to 4-bit binary

    return hex_to_binary_array(sha256_hash)


def bits_to_hexdigest(bits):
    """
    Converts a NumPy array of bits to a hexdigest string.

    Args:
        bits: A NumPy array of bits representing a SHA256 hash.

    Returns:
        The hexdigest string.
    """
    hex_digits = []
    for i in range(0, len(bits), 4):
        four_bits = bits[i:i+4]
        four_bits = map(int, four_bits)
        hex_value = int("".join(map(str, four_bits)), 2)
        hex_digits.append(hex(hex_value)[2:].zfill(1))  # Convert 4 bits to hex digit
    return "".join(hex_digits)


def hex_to_binary_array(hex_string):
    """
    Converts a hexadecimal string to a NumPy array of binary bits.

    Args:
        hex_string: The hexadecimal string to convert.

    Returns:
        A NumPy array representing the binary bits.
    """
    scale = 16 ## equals to hexadecimal
    num_of_bits = 4
    bits = []
    for char in hex_string:
        hex_value = int(char, scale)
        bits.extend([int(bit) for bit in bin(hex_value)[2:].zfill(num_of_bits)])
    return np.array(bits)


def compute_hash(data: Union[np.ndarray, Image.Image]) -> str:
    """Compute SHA-256 hash of image data."""
    if isinstance(data, np.ndarray):
        data_bytes = data.tobytes()
    else:
        data_bytes = data.tobytes()
    return hashlib.sha256(data_bytes).hexdigest()


def generate_watermark(message: str, secret_key: str) -> np.ndarray:
    """Generate watermark from message and secret key."""
    combined_input = message + secret_key
    return string_to_sha256_bits(combined_input)


def get_image_files(supported_formats, directory: str) -> List[Path]:
    """
    Get all supported image files from directory.

    Args:
        directory: Directory path to scan for images

    Returns:
        List of Path objects for valid image files
        :param directory:
        :param supported_formats:
    """
    directory_path = Path(directory)
    if not directory_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    image_files = []
    for ext in supported_formats:
        image_files.extend(directory_path.glob(f"*{ext}"))

    return sorted(set(image_files))
