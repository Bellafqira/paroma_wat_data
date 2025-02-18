from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from configs.gen_wat_cfs import ConfigGenerator
from watermarking.watermark_embedder_batch import BatchEmbedderProcessor
from watermarking.watermark_extractor import WatermarkExtractor
from watermarking.watermark_remover_batch import BatchRemoveProcessor

app = FastAPI(
    title="Watermarking API",
    description="API for image watermarking operations with blockchain integration",
    version="1.0.0"
)


# Models for request validation
class EmbedRequest(BaseModel):
    data_path: str
    save_path: str
    message: str
    data_type: str = "dcm"
    kernel: Optional[List[List[float]]] = None
    stride: int = 3
    t_hi: float = 0
    bit_depth: int = 16


class ExtractRequest(BaseModel):
    data_path: str
    data_type: str = "dcm"


class RemoveRequest(BaseModel):
    data_path: str
    save_path: str
    ext_wat_path: str
    data_type: str = "dcm"


# Initialize ConfigGenerator
config_generator = ConfigGenerator()


@app.post("/api/generate-config/embed")
async def generate_embed_config(request: EmbedRequest):
    try:
        config = config_generator.generate_embed_config(
            data_path=request.data_path,
            save_path=request.save_path,
            message=request.message,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type,
            kernel=request.kernel,
            stride=request.stride,
            t_hi=request.t_hi,
            bit_depth=request.bit_depth
        )
        return {"status": "success", "config": config.__dict__}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate-config/extract")
async def generate_extract_config(request: ExtractRequest):
    try:
        config = config_generator.generate_extract_config(
            data_path=request.data_path,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type
        )
        return {"status": "success", "config": config.__dict__}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate-config/remove")
async def generate_remove_config(request: RemoveRequest):
    try:
        config = config_generator.generate_remove_config(
            data_path=request.data_path,
            save_path=request.save_path,
            ext_wat_path=request.ext_wat_path,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type
        )
        return {"status": "success", "config": config.__dict__}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/watermark/embed")
async def embed_watermark(request: EmbedRequest):
    try:
        # Generate config
        config = config_generator.generate_embed_config(
            data_path=request.data_path,
            save_path=request.save_path,
            message=request.message,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type,
            kernel=request.kernel,
            stride=request.stride,
            t_hi=request.t_hi,
            bit_depth=request.bit_depth
        )

        # Process embedding
        processor = BatchEmbedderProcessor(config)
        result = processor.process_images()

        return {
            "status": "success",
            "processed_images": result.processed_images,
            "total_images": result.total_images,
            "failed_images": result.failed_images,
            "processing_time": result.processing_time
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/watermark/extract")
async def extract_watermark(request: ExtractRequest):
    try:
        # Generate config
        config = config_generator.generate_extract_config(
            data_path=request.data_path,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type
        )

        # Process extraction
        extractor = WatermarkExtractor(config)
        result = extractor.extract()

        return {
            "status": "success",
            "extraction_result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/watermark/remove")
async def remove_watermark(request: RemoveRequest):
    try:
        # Generate config
        config = config_generator.generate_remove_config(
            data_path=request.data_path,
            save_path=request.save_path,
            ext_wat_path=request.ext_wat_path,
            blockchain_path="blockchain/database/blockchainDB.json",
            data_type=request.data_type
        )

        # Process removal
        processor = BatchRemoveProcessor(config)
        result = processor.process_images()

        return {
            "status": "success",
            "processed_images": result.processed_images,
            "total_images": result.total_images,
            "failed_images": result.failed_images,
            "average_ber": result.average_ber,
            "processing_time": result.processing_time
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
