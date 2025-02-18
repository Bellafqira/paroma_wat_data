import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import hashlib
from dataclasses import dataclass, asdict


@dataclass
class BlockHeader:
    """Block header containing metadata"""
    timestamp: float
    previous_hash: str
    block_number: int

    def to_dict(self) -> dict:
        """Convert header to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'BlockHeader':
        """Create header from dictionary."""
        return cls(**data)


@dataclass
class Block:
    """Block class for watermarking transactions"""

    header: BlockHeader
    info: str
    transaction: dict  # Single watermark transaction
    hash: Optional[str] = None

    def calculate_hash(self) -> str:
        """Calculate block hash including header and transaction."""
        block_dict = {
            'header': self.header.to_dict(),
            'info': self.info,
            'transaction': self.transaction,
        }
        block_string = json.dumps(block_dict, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def finalize_block(self) -> None:
        """Finalize the block by calculating its hash."""
        self.hash = self.calculate_hash()

    def to_dict(self) -> dict:
        """Convert block to dictionary."""
        return {
            'header': self.header.to_dict(),
            'info': self.info,
            'transaction': self.transaction,
            'hash': self.hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        """Create block from dictionary."""
        header = BlockHeader.from_dict(data['header'])
        return cls(
            header=header,
            info=data['info'],
            transaction=data['transaction'],
            hash=data['hash']
        )


class Blockchain:
    def __init__(self, blockchain_file: str = "blockchainDB_2.json"):
        self.blockchain_file = Path(blockchain_file)
        self.blocks: Dict[str, Block] = {}
        self.load_blockchain()

        # Create genesis block if blockchain is empty
        if not self.blocks:
            self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        """Create and store the genesis block."""
        header = BlockHeader(
            timestamp=datetime.now().timestamp(),
            previous_hash="0" * 64,  # 64 zeros for genesis block
            block_number=0
        )

        genesis_block = Block(
            header=header,
            info="None",
            transaction={}  # Empty transaction for genesis block
        )
        genesis_block.finalize_block()

        # Add genesis block
        self.blocks["0"] = genesis_block
        self.save_blockchain()
        print("Genesis block created and saved")

    def load_blockchain(self) -> None:
        """Load blockchain from file."""
        if self.blockchain_file.exists():
            try:
                with open(self.blockchain_file, 'r') as f:
                    blockchain_data = json.load(f)
                    self.blocks = {
                        block_num: Block.from_dict(block_data)
                        for block_num, block_data in blockchain_data.items()
                    }
            except json.JSONDecodeError:
                print("Error loading blockchain file. Creating new blockchain.")
                self.blocks = {}
        else:
            self.blocks = {}

    def save_blockchain(self) -> None:
        """Save blockchain to file."""
        blockchain_data = {
            block_num: block.to_dict()
            for block_num, block in self.blocks.items()
        }

        # Create directory if it doesn't exist
        self.blockchain_file.parent.mkdir(parents=True, exist_ok=True)

        # Save with pretty printing
        with open(self.blockchain_file, 'w') as f:
            json.dump(blockchain_data, f, indent=2)

    def get_latest_block_number(self) -> int:
        """Get the number of the latest block."""
        if not self.blocks:
            return -1
        return max(int(num) for num in self.blocks.keys())

    def add_transaction(self, transaction: dict, info: str) -> Block:
        """
        Add a transaction by creating a new block.
        Returns the new block.
        """
        latest_block_num = self.get_latest_block_number()
        new_block_num = latest_block_num + 1

        # Get previous block's hash
        previous_hash = self.blocks[str(latest_block_num)].hash

        # Create new block
        header = BlockHeader(
            timestamp=datetime.now().timestamp(),
            previous_hash=previous_hash,
            block_number=new_block_num
        )

        new_block = Block(
            header=header,
            info=info,
            transaction=transaction
        )

        # Finalize and save block
        new_block.finalize_block()
        self.blocks[str(new_block_num)] = new_block
        self.save_blockchain()

        return new_block

    def verify_chain(self) -> bool:
        """Verify the integrity of the blockchain."""
        for i in range(1, len(self.blocks)):
            current_block = self.blocks[str(i)]
            previous_block = self.blocks[str(i - 1)]

            # Verify block links
            if current_block.header.previous_hash != previous_block.hash:
                return False

            # Verify block hash
            if current_block.hash != current_block.calculate_hash():
                return False

        return True

    def get_block(self, block_number: int) -> Optional[Block]:
        """Get a block by its number."""
        return self.blocks.get(str(block_number))

    def get_transaction_history(self, image_hash: str):
        """Get all transactions related to a specific image."""
        history = {}
        transaction_current = {}
        for block_num, block in self.blocks.items():
            if block.info == "embedder":
                for idx, transaction in block.transaction["transaction_dict"].items():
                    if transaction and (
                            transaction['hash_image_wat'] == image_hash

                    ):
                        transaction_current = transaction
                        history = {
                            'block_number': block_num,
                            'block_hash': block.hash,
                            'timestamp': block.header.timestamp,
                            'info': block.info,
                            'image_hash': transaction['hash_image_wat']
                        }
                        break
        return history, transaction_current



