import os
from pathlib import Path
from typing import Dict, List, Optional, Set
import json
from datetime import datetime
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor
import logging
from tqdm import tqdm

from PIL import Image

from watermarking.utils import get_image_files
from watermarking.watermark_remover import WatermarkRemove
from blockchain.blockchain import Blockchain


@dataclass
class BatchRemoveTransaction:
    """Data class for batch transaction"""
    processing_time: float
    total_images: int = 0
    processed_images: int = 0
    failed_images: List[str] = None
    transaction_dict: Dict[str, dict] = None
    average_ber: float = 0.5


class BatchRemoveProcessor:
    def __init__(self, config):
        self.config = config
        self.supported_formats: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.dcm'}
        self.blockchain = Blockchain(config.blockchain_path)

    def process_single_image(self, img_path: Path, rec_path: Path, wat_path: Path) -> tuple:
        """Process a single image and return results."""
        try:
            # Update config for current image
            self.config.data_path = str(img_path)
            save_name = f"recovered_{img_path.name}"
            self.config.save_path = str(rec_path) + "/" + save_name
            self.config.ext_wat_path = str(wat_path) + '.npy'

            # Create extractor and process image
            extractor = WatermarkRemove(self.config)
            result = extractor.extract_and_remove()

            return (
                img_path,
                True,
                result.transaction,
                result.ber
            )

        except Exception as e:
            print(f"Error processing {img_path.name}: {str(e)}")
            return img_path, False, None, None

    def process_images(self) -> BatchRemoveTransaction:
        """Process all images in the configured directory."""
        start_time = datetime.now()

        # Get all image files
        try:
            image_files = get_image_files(self.supported_formats, self.config.data_path)
            total_images = len(image_files)

            if not total_images:
                raise ValueError(f"No supported images found in {self.config.data_path}")

            # Create save directory
            save_path = Path(self.config.save_path)
            ext_wat_path = Path(self.config.ext_wat_path)
            save_path.mkdir(parents=True, exist_ok=True)
            ext_wat_path.mkdir(parents=True, exist_ok=True)

            # Process images using thread pool
            successful_extractions = {}
            failed_images = []
            image_transactions = {}

            with ThreadPoolExecutor() as executor:
                # futures = [executor.submit(self.process_single_image, img_path)
                #            for img_path in image_files]

                futures = [self.process_single_image(img_path, save_path, ext_wat_path)
                           for img_path in image_files]

                # Process results with progress bar
                for future in tqdm(futures, total=len(futures), desc="Processing images"):
                    img_path, success, transaction, ber = future  # .result()

                    if success:
                        image_hash = transaction["watermarked_image_hash"]
                        successful_extractions[image_hash] = ber
                        image_transactions[image_hash] = transaction
                    else:
                        failed_images.append(str(img_path))

            # Calculate statistics
            processed_images = len(successful_extractions)
            average_ber = (sum(successful_extractions.values()) / processed_images
                           if processed_images > 0 else 0.0)

            processing_time = (datetime.now() - start_time).total_seconds()

            # Create batch transaction
            batch_transaction = BatchRemoveTransaction(
                total_images=total_images,
                processed_images=processed_images,
                failed_images=failed_images,
                processing_time=processing_time,
                average_ber=average_ber,
                transaction_dict=image_transactions,
            )

            # # Add to blockchain
            new_block = self.blockchain.add_transaction(asdict(batch_transaction), info="remover")

            # Verify chain
            is_valid = self.blockchain.verify_chain()
            print(f"\nBlockchain is valid: {is_valid}")

            print(f"\nNew block created:")
            print(f"Block number: {new_block.header.block_number}")
            print(f"Block hash: {new_block.hash}")
            print(f"Timestamp: {datetime.fromtimestamp(new_block.header.timestamp)}")

            print(f"\nBatch embedding completed in {processing_time:.2f} seconds")
            print(f"Successfully processed: {processed_images}/{total_images} images")

            if failed_images:
                print(f"Failed to process {len(failed_images)} images")

            return batch_transaction

        except Exception as e:
            print(f"Batch processing failed: {str(e)}")
            raise

