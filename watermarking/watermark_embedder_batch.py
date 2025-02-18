import os
from pathlib import Path
from typing import Dict, List, Optional, Set
import json
from datetime import datetime
from dataclasses import asdict, dataclass
from PIL import Image
from tqdm import tqdm

from blockchain.blockchain import Blockchain
from watermarking.utils import get_image_files
from watermarking.watermark_embedder import WatermarkEmbedder


@dataclass
class BatchEmbedTransaction:
    """Data class for batch processing results"""
    processing_time: float
    total_images: int = 0
    processed_images: int = 0
    failed_images: List[str] = None
    transaction_dict: Dict[str, dict] = None


class BatchEmbedderProcessor:
    def __init__(self, config):
        self.config = config
        self.supported_formats: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.dcm'}
        self.embedder = WatermarkEmbedder(config)
        self.transaction_dict = {}
        self.blockchain = Blockchain(config.blockchain_path)

    def process_images(self) -> BatchEmbedTransaction:
        """
        Process all images in the configured directory.

        Returns:
            BatchProcessingResult with processing statistics and transaction dictionary
        """
        start_time = datetime.now()

        # Get all image files
        try:
            image_files = get_image_files(self.supported_formats, self.config.data_path)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error accessing image directory: {str(e)}")

        if not image_files:
            raise ValueError(f"No supported images found in {self.config.data_path}")

        total_images = len(image_files)
        processed_images = 0
        failed_images = []

        # Create save directory if it doesn't exist
        save_path = Path(self.config.save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        print(f"Starting batch processing of {total_images} images...")

        # Process each image
        for img_path in tqdm(image_files, total=len(image_files), desc="Processing images"):
            try:
                print(f"\nProcessing image: {img_path.name}")

                # Update config with current image paths
                self.config.data_path = str(img_path)
                self.config.save_path = str(save_path / f"watermarked_{img_path.name}")

                # Embed watermark
                transaction = self.embedder.embed_watermarks()

                # Store transaction in dictionary using watermarked image hash as key
                self.transaction_dict[transaction.hash_image_wat] = asdict(transaction)

                processed_images += 1
                print(f"Successfully processed: {img_path.name}")

            except Exception as e:
                print(f"Error processing {img_path.name}: {str(e)}")
                failed_images.append(str(img_path))

        processing_time = (datetime.now() - start_time).total_seconds()

        # Create result object
        batch_transaction = BatchEmbedTransaction(
            total_images=total_images,
            processed_images=processed_images,
            failed_images=failed_images,
            processing_time=processing_time,
            transaction_dict=self.transaction_dict,
        )

        # # Save transaction dictionary in the blockchain
        # Add transaction
        new_block = self.blockchain.add_transaction(asdict(batch_transaction), info="embedder")

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
