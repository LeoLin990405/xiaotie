"""
多模态支持系统

实现图像、音频、视频等多模态数据处理能力
"""

import asyncio
import base64
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
import numpy as np

from ..schema import Message, ToolResult
from ..tools.base import Tool


class ModalityType(Enum):
    """模态类型"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    CODE = "code"


class MediaType(Enum):
    """媒体类型"""
    PNG = "png"
    JPEG = "jpeg"
    GIF = "gif"
    MP3 = "mp3"
    WAV = "wav"
    MP4 = "mp4"
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


@dataclass
class MediaContent:
    """媒体内容"""
    modality: ModalityType
    content: Union[str, bytes, np.ndarray]  # 根据模态类型变化
    media_type: Optional[MediaType] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class BaseMultimodalProcessor(ABC):
    """多模态处理器基类"""
    
    @abstractmethod
    async def encode(self, content: MediaContent) -> bytes:
        """编码媒体内容"""
        pass
    
    @abstractmethod
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码媒体内容"""
        pass
    
    @abstractmethod
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理媒体内容"""
        pass


class TextProcessor(BaseMultimodalProcessor):
    """文本处理器"""
    
    async def encode(self, content: MediaContent) -> bytes:
        """编码文本内容"""
        if isinstance(content.content, str):
            return content.content.encode('utf-8')
        elif isinstance(content.content, bytes):
            return content.content
        else:
            return str(content.content).encode('utf-8')
    
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码文本内容"""
        text_content = encoded_data.decode('utf-8')
        return MediaContent(
            modality=ModalityType.TEXT,
            content=text_content,
            media_type=MediaType.TXT
        )
    
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理文本内容"""
        text = content.content if isinstance(content.content, str) else str(content.content)
        
        # 简单的文本分析
        word_count = len(text.split())
        char_count = len(text)
        line_count = len(text.split('\n'))
        
        # 提取关键词（简单实现）
        words = text.lower().split()
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in set(words) if word not in common_words and len(word) > 3]
        
        return {
            "modality": content.modality.value,
            "word_count": word_count,
            "char_count": char_count,
            "line_count": line_count,
            "keywords": keywords[:10],  # 限制关键词数量
            "language": "zh-CN"  # 简化实现，总是返回中文
        }


class ImageProcessor(BaseMultimodalProcessor):
    """图像处理器"""
    
    async def encode(self, content: MediaContent) -> bytes:
        """编码图像内容"""
        if isinstance(content.content, str):
            # 如果是base64字符串，先解码
            try:
                return base64.b64decode(content.content)
            except:
                # 如果不是base64，当作文件路径处理
                with open(content.content, 'rb') as f:
                    return f.read()
        elif isinstance(content.content, bytes):
            return content.content
        elif isinstance(content.content, Image.Image):
            # 将PIL图像转换为bytes
            img_buffer = io.BytesIO()
            content.content.save(img_buffer, format='PNG')
            return img_buffer.getvalue()
        else:
            raise ValueError(f"不支持的图像内容类型: {type(content.content)}")
    
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码图像内容"""
        # 创建PIL图像对象
        image = Image.open(io.BytesIO(encoded_data))
        return MediaContent(
            modality=ModalityType.IMAGE,
            content=image,
            media_type=MediaType.PNG  # 简化实现
        )
    
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理图像内容"""
        if isinstance(content.content, str):
            # 如果是文件路径或base64字符串，先转换为Image对象
            if content.content.startswith('data:image'):
                # base64图像数据
                header, encoded = content.content.split(',', 1)
                image_data = base64.b64decode(encoded)
                image = Image.open(io.BytesIO(image_data))
            else:
                # 文件路径
                image = Image.open(content.content)
        elif isinstance(content.content, bytes):
            # 字节数据
            image = Image.open(io.BytesIO(content.content))
        elif isinstance(content.content, Image.Image):
            # PIL图像对象
            image = content.content
        else:
            raise ValueError(f"不支持的图像内容类型: {type(content.content)}")
        
        # 获取图像信息
        width, height = image.size
        mode = image.mode
        format = image.format or "UNKNOWN"
        
        # 简单的图像分析
        pixels = np.array(image)
        channels = pixels.shape[2] if len(pixels.shape) > 2 else 1
        
        return {
            "modality": content.modality.value,
            "width": width,
            "height": height,
            "mode": mode,
            "format": format,
            "channels": channels,
            "size_estimate": f"{width}x{height}",
            "is_color": mode in ['RGB', 'RGBA', 'CMYK', 'YCbCr', 'LAB', 'HSV']
        }


class AudioProcessor(BaseMultimodalProcessor):
    """音频处理器"""
    
    async def encode(self, content: MediaContent) -> bytes:
        """编码音频内容"""
        if isinstance(content.content, str):
            # 文件路径
            with open(content.content, 'rb') as f:
                return f.read()
        elif isinstance(content.content, bytes):
            return content.content
        else:
            raise ValueError(f"不支持的音频内容类型: {type(content.content)}")
    
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码音频内容"""
        return MediaContent(
            modality=ModalityType.AUDIO,
            content=encoded_data,
            media_type=MediaType.MP3  # 简化实现
        )
    
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理音频内容（简化实现）"""
        # 这有实际的音频处理库，返回基本信息
        if isinstance(content.content, str):
            # 假设是文件路径
            import os
            size = os.path.getsize(content.content) if os.path.exists(content.content) else len(content.content)
        elif isinstance(content.content, bytes):
            size = len(content.content)
        else:
            size = 0
        
        return {
            "modality": content.modality.value,
            "size_bytes": size,
            "estimated_duration": "unknown",  # 简化实现
            "sample_rate": "unknown",
            "channels": "unknown"
        }


class VideoProcessor(BaseMultimodalProcessor):
    """视频处理器"""
    
    async def encode(self, content: MediaContent) -> bytes:
        """编码视频内容"""
        if isinstance(content.content, str):
            # 文件路径
            with open(content.content, 'rb') as f:
                return f.read()
        elif isinstance(content.content, bytes):
            return content.content
        else:
            raise ValueError(f"不支持的视频内容类型: {type(content.content)}")
    
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码视频内容"""
        return MediaContent(
            modality=ModalityType.VIDEO,
            content=encoded_data,
            media_type=MediaType.MP4  # 简化实现
        )
    
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理视频内容（简化实现）"""
        if isinstance(content.content, str):
            import os
            size = os.path.getsize(content.content) if os.path.exists(content.content) else len(content.content)
        elif isinstance(content.content, bytes):
            size = len(content.content)
        else:
            size = 0
        
        return {
            "modality": content.modality.value,
            "size_bytes": size,
            "estimated_duration": "unknown",
            "resolution": "unknown",
            "fps": "unknown"
        }


class DocumentProcessor(BaseMultimodalProcessor):
    """文档处理器"""
    
    async def encode(self, content: MediaContent) -> bytes:
        """编码文档内容"""
        if isinstance(content.content, str):
            # 文件路径或文本内容
            if content.content.startswith('/'):  # 假设以/开头的是文件路径
                with open(content.content, 'rb') as f:
                    return f.read()
            else:
                return content.content.encode('utf-8')
        elif isinstance(content.content, bytes):
            return content.content
        else:
            return str(content.content).encode('utf-8')
    
    async def decode(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码文档内容"""
        text_content = encoded_data.decode('utf-8')
        return MediaContent(
            modality=ModalityType.DOCUMENT,
            content=text_content,
            media_type=MediaType.TXT
        )
    
    async def process(self, content: MediaContent) -> Dict[str, Any]:
        """处理文档内容"""
        if isinstance(content.content, bytes):
            text = content.content.decode('utf-8')
        elif isinstance(content.content, str):
            text = content.content
        else:
            text = str(content.content)
        
        # 简单的文档分析
        word_count = len(text.split())
        char_count = len(text)
        page_count = len(text.split('\f'))  # 假设\f是分页符
        
        return {
            "modality": content.modality.value,
            "word_count": word_count,
            "char_count": char_count,
            "page_count": page_count,
            "contains_images": "![image]" in text or "<img" in text,
            "contains_tables": "|" in text or "<table" in text
        }


class MultimodalContentManager:
    """多模态内容管理器"""
    
    def __init__(self):
        self.processors = {
            ModalityType.TEXT: TextProcessor(),
            ModalityType.IMAGE: ImageProcessor(),
            ModalityType.AUDIO: AudioProcessor(),
            ModalityType.VIDEO: VideoProcessor(),
            ModalityType.DOCUMENT: DocumentProcessor(),
        }
        
        # 内容缓存
        self.content_cache: Dict[str, MediaContent] = {}
        
        # 处理历史
        self.processing_history: List[Dict[str, Any]] = []
    
    async def register_processor(self, modality: ModalityType, processor: BaseMultimodalProcessor):
        """注册新的处理器"""
        self.processors[modality] = processor
    
    async def add_content(self, content: MediaContent) -> str:
        """添加内容到管理器"""
        import uuid
        content_id = str(uuid.uuid4())
        self.content_cache[content_id] = content
        
        return content_id
    
    async def get_content(self, content_id: str) -> Optional[MediaContent]:
        """获取内容"""
        return self.content_cache.get(content_id)
    
    async def process_content(self, content: MediaContent) -> Dict[str, Any]:
        """处理内容"""
        if content.modality not in self.processors:
            raise ValueError(f"不支持的模态类型: {content.modality}")
        
        processor = self.processors[content.modality]
        result = await processor.process(content)
        
        # 记录处理历史
        history_entry = {
            "content_id": str(hash(content.content)),  # 使用内容的哈希作为ID
            "modality": content.modality.value,
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        self.processing_history.append(history_entry)
        
        # 保持历史记录在合理范围内
        if len(self.processing_history) > 1000:
            self.processing_history = self.processing_history[-500:]
        
        return result
    
    async def encode_content(self, content: MediaContent) -> bytes:
        """编码内容"""
        if content.modality not in self.processors:
            raise ValueError(f"不支持的模态类型: {content.modality}")
        
        processor = self.processors[content.modality]
        return await processor.encode(content)
    
    async def decode_content(self, encoded_data: bytes, modality: ModalityType) -> MediaContent:
        """解码内容"""
        if modality not in self.processors:
            raise ValueError(f"不支持的模态类型: {modality}")
        
        processor = self.processors[modality]
        return await processor.decode(encoded_data, modality)
    
    async def get_content_summary(self, content_id: str) -> Optional[Dict[str, Any]]:
        """获取内容摘要"""
        content = await self.get_content(content_id)
        if not content:
            return None
        
        return await self.process_content(content)
    
    async def search_content(self, query: str, modality: Optional[ModalityType] = None) -> List[str]:
        """搜索内容"""
        results = []
        
        for content_id, content in self.content_cache.items():
            # 对于文本和文档，进行内容搜索
            if content.modality in [ModalityType.TEXT, ModalityType.DOCUMENT]:
                if isinstance(content.content, str) and query.lower() in content.content.lower():
                    results.append(content_id)
            elif content.modality == ModalityType.IMAGE and query.lower() in "image picture photo".split():
                # 简化图像搜索
                results.append(content_id)
        
        return results
    
    async def get_multimodal_analysis(self, content_ids: List[str]) -> Dict[str, Any]:
        """获取多模态内容分析"""
        analysis = {
            "total_contents": len(content_ids),
            "modality_distribution": {},
            "processing_results": {}
        }
        
        for content_id in content_ids:
            content = await self.get_content(content_id)
            if content:
                # 更新模态分布
                modality = content.modality.value
                analysis["modality_distribution"][modality] = \
                    analysis["modality_distribution"].get(modality, 0) + 1
                
                # 获取处理结果
                result = await self.process_content(content)
                analysis["processing_results"][content_id] = result
        
        return analysis
    
    async def clear_cache(self):
        """清空缓存"""
        self.content_cache.clear()
        self.processing_history.clear()


class MultimodalAgentMixin:
    """多模态Agent混入类"""
    
    def __init__(self, multimodal_manager: MultimodalContentManager):
        self.multimodal_manager = multimodal_manager
        self.multimodal_enabled = True
    
    async def enable_multimodal(self):
        """启用多模态功能"""
        self.multimodal_enabled = True
    
    async def disable_multimodal(self):
        """禁用多模态功能"""
        self.multimodal_enabled = False
    
    async def process_multimodal_input(self, inputs: List[Union[str, MediaContent]]) -> List[Dict[str, Any]]:
        """处理多模态输入"""
        if not self.multimodal_enabled:
            return [{"error": "多模态功能已禁用"}]
        
        results = []
        
        for inp in inputs:
            if isinstance(inp, str):
                # 如果是字符串，假设是文本内容
                content = MediaContent(modality=ModalityType.TEXT, content=inp)
            elif isinstance(inp, MediaContent):
                content = inp
            else:
                results.append({"error": f"不支持的输入类型: {type(inp)}"})
                continue
            
            try:
                result = await self.multimodal_manager.process_content(content)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return results
    
    async def analyze_image(self, image_source: Union[str, bytes, Image.Image]) -> Dict[str, Any]:
        """分析图像"""
        if not self.multimodal_enabled:
            return {"error": "多模态功能已禁用"}
        
        content = MediaContent(modality=ModalityType.IMAGE, content=image_source)
        return await self.multimodal_manager.process_content(content)
    
    async def analyze_document(self, doc_source: Union[str, bytes]) -> Dict[str, Any]:
        """分析文档"""
        if not self.multimodal_enabled:
            return {"error": "多模态功能已禁用"}
        
        content = MediaContent(modality=ModalityType.DOCUMENT, content=doc_source)
        return await self.multimodal_manager.process_content(content)
    
    async def get_multimodal_capabilities(self) -> Dict[str, List[str]]:
        """获取多模态能力"""
        return {
            "supported_modalities": [m.value for m in self.multimodal_manager.processors.keys()],
            "supported_media_types": [
                "png", "jpeg", "gif", "mp3", "wav", "mp4", "pdf", "docx", "txt"
            ],
            "processing_functions": [
                "analyze_image",
                "analyze_document",
                "process_multimodal_input",
                "search_content"
            ]
        }
    
    async def search_multimodal_content(self, query: str) -> List[Dict[str, Any]]:
        """搜索多模态内容"""
        if not self.multimodal_enabled:
            return []
        
        content_ids = await self.multimodal_manager.search_content(query)
        results = []
        
        for cid in content_ids:
            summary = await self.multimodal_manager.get_content_summary(cid)
            if summary:
                results.append({
                    "content_id": cid,
                    "summary": summary
                })
        
        return results
    
    async def get_multimodal_analytics(self) -> Dict[str, Any]:
        """获取多模态分析"""
        return {
            "enabled": self.multimodal_enabled,
            "supported_modalities": list(self.multimodal_manager.processors.keys()),
            "cached_contents": len(self.multimodal_manager.content_cache),
            "processing_history_count": len(self.multimodal_manager.processing_history)
        }


class ImageAnalysisTool(Tool):
    """图像分析工具"""
    
    @property
    def name(self) -> str:
        return "image_analyzer"
    
    @property
    def description(self) -> str:
        return "分析图像内容，提取图像信息如尺寸、格式、颜色等"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_data": {
                    "type": "string",
                    "description": "图像的base64编码数据或文件路径"
                }
            },
            "required": ["image_data"]
        }
    
    def __init__(self):
        super().__init__()
        self.manager = MultimodalContentManager()
    
    async def execute(self, image_data: str) -> ToolResult:
        """执行图像分析"""
        try:
            content = MediaContent(
                modality=ModalityType.IMAGE,
                content=image_data
            )
            
            result = await self.manager.process_content(content)
            
            analysis = (
                f"图像分析结果:\n"
                f"- 尺寸: {result.get('size_estimate', 'Unknown')}\n"
                f"- 格式: {result.get('format', 'Unknown')}\n"
                f"- 模式: {result.get('mode', 'Unknown')}\n"
                f"- 通道数: {result.get('channels', 'Unknown')}\n"
                f"- 是否彩色: {result.get('is_color', 'Unknown')}"
            )
            
            return ToolResult(success=True, content=analysis)
        except Exception as e:
            return ToolResult(success=False, error=f"图像分析失败: {str(e)}")


class DocumentAnalysisTool(Tool):
    """文档分析工具"""
    
    @property
    def name(self) -> str:
        return "document_analyzer"
    
    @property
    def description(self) -> str:
        return "分析文档内容，提取文档信息如字数、页数、表格图片等"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "document_data": {
                    "type": "string",
                    "description": "文档的文本内容或文件路径"
                }
            },
            "required": ["document_data"]
        }
    
    def __init__(self):
        super().__init__()
        self.manager = MultimodalContentManager()
    
    async def execute(self, document_data: str) -> ToolResult:
        """执行文档分析"""
        try:
            content = MediaContent(
                modality=ModalityType.DOCUMENT,
                content=document_data
            )
            
            result = await self.manager.process_content(content)
            
            analysis = (
                f"文档分析结果:\n"
                f"- 字数: {result.get('word_count', 'Unknown')}\n"
                f"- 字符数: {result.get('char_count', 'Unknown')}\n"
                f"- 页数: {result.get('page_count', 'Unknown')}\n"
                f"- 包含图片: {result.get('contains_images', 'Unknown')}\n"
                f"- 包含表格: {result.get('contains_tables', 'Unknown')}"
            )
            
            return ToolResult(success=True, content=analysis)
        except Exception as e:
            return ToolResult(success=False, error=f"文档分析失败: {str(e)}")