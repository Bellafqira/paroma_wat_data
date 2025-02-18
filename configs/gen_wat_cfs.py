from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional, Union, Dict, Any, List


@dataclass
class EmbedConfig:
    data_path: str
    save_path: str
    blockchain_path: str
    message: str
    kernel: List[List[float]]
    stride: int
    t_hi: float
    bit_depth: int
    data_type: str
    operation_type: str = "embedding"


@dataclass
class ExtractConfig:
    data_path: str
    blockchain_path: str
    data_type: str
    operation_type: str = "extraction"


@dataclass
class RemoveConfig:
    data_path: str
    save_path: str
    ext_wat_path: str
    blockchain_path: str
    data_type: str
    operation_type: str = "removal"


class ConfigGenerator:
    DEFAULT_KERNEL = [[0, 1 / 4, 0], [1 / 4, 0, 1 / 4], [0, 1 / 4, 0]]

    def __init__(self, config_dir: str = "configs/database"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _save_config(self, config: Union[Dict, Any], filename: str) -> None:
        """Save configuration to JSON file."""
        if hasattr(config, '__dict__'):
            config_dict = config.__dict__
        else:
            config_dict = config

        config_path = self.config_dir / f"{filename}.json"
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=4)

    def _load_config(self, filename: str) -> Dict:
        """Load configuration from JSON file."""
        config_path = self.config_dir / f"{filename}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            return json.load(f)

    def _validate_paths(self, paths: Dict[str, str]) -> None:
        """Validate and create paths if they don't exist."""
        for path_name, path_value in paths.items():
            if path_value:
                path_obj = Path(path_value)
                path_obj.parent.mkdir(parents=True, exist_ok=True)

    def generate_embed_config(
            self,
            data_path: str,
            save_path: str,
            message: str,
            blockchain_path: str,
            data_type: str = "dcm",
            kernel: Optional[List[List[float]]] = None,
            stride: int = 3,
            t_hi: float = 0,
            bit_depth: int = 16,
            filename: str = "embed_config"
    ) -> EmbedConfig:
        """Generate embedding configuration."""
        # Validate paths
        self._validate_paths({
            'data_path': data_path,
            'save_path': save_path,
            'blockchain_path': blockchain_path
        })

        config = EmbedConfig(
            data_path=data_path,
            save_path=save_path,
            blockchain_path=blockchain_path,
            message=message,
            kernel=kernel if kernel is not None else self.DEFAULT_KERNEL,
            stride=stride,
            t_hi=t_hi,
            bit_depth=bit_depth,
            data_type=data_type
        )

        self._save_config(config, filename)
        return config

    def generate_extract_config(
            self,
            data_path: str,
            blockchain_path: str,
            data_type: str = "dcm",
            filename: str = "extract_config"
    ) -> ExtractConfig:
        """Generate extraction configuration."""
        # Validate paths
        self._validate_paths({
            'data_path': data_path,
            'blockchain_path': blockchain_path
        })

        config = ExtractConfig(
            data_path=data_path,
            blockchain_path=blockchain_path,
            data_type=data_type
        )

        self._save_config(config, filename)
        return config

    def generate_remove_config(
            self,
            data_path: str,
            save_path: str,
            ext_wat_path: str,
            blockchain_path: str,
            data_type: str = "dcm",
            filename: str = "remove_config"
    ) -> RemoveConfig:
        """Generate removal configuration."""
        # Validate paths
        self._validate_paths({
            'data_path': data_path,
            'save_path': save_path,
            'ext_wat_path': ext_wat_path,
            'blockchain_path': blockchain_path
        })

        config = RemoveConfig(
            data_path=data_path,
            save_path=save_path,
            ext_wat_path=ext_wat_path,
            blockchain_path=blockchain_path,
            data_type=data_type
        )

        self._save_config(config, filename)
        return config

    def load_embed_config(self, filename: str = "embed_config") -> EmbedConfig:
        """Load embedding configuration."""
        config_dict = self._load_config(filename)
        return EmbedConfig(**config_dict)

    def load_extract_config(self, filename: str = "extract_config") -> ExtractConfig:
        """Load extraction configuration."""
        config_dict = self._load_config(filename)
        return ExtractConfig(**config_dict)

    def load_remove_config(self, filename: str = "remove_config") -> RemoveConfig:
        """Load removal configuration."""
        config_dict = self._load_config(filename)
        return RemoveConfig(**config_dict)

