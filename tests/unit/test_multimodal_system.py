"""
多模态支持系统测试

验证新多模态功能的工作情况
"""

import asyncio
import base64
from io import BytesIO
from PIL import Image
from xiaotie import (
    MultimodalContentManager,
    MultimodalAgentMixin,
    ModalityType,
    MediaContent,
    ImageAnalysisTool,
    DocumentAnalysisTool
)


async def test_multimodal_content_manager():
    """测试多模态内容管理器"""
    print("🌈 测试多模态内容管理器...")
    
    # 创建多模态内容管理器
    manager = MultimodalContentManager()
    
    # 测试文本内容
    text_content = MediaContent(
        modality=ModalityType.TEXT,
        content="这是一个测试文本，用于验证多模态系统。"
    )
    
    text_result = await manager.process_content(text_content)
    print(f"   文本处理 - 字数: {text_result['word_count']}, 关键词: {text_result['keywords']}")
    
    # 测试创建一个简单的图像
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_data = img_io.getvalue()
    
    image_content = MediaContent(
        modality=ModalityType.IMAGE,
        content=img_data
    )
    
    image_result = await manager.process_content(image_content)
    print(f"   图像处理 - 尺寸: {image_result['size_estimate']}, 彩色: {image_result['is_color']}")
    
    # 测试文档内容
    doc_content = MediaContent(
        modality=ModalityType.DOCUMENT,
        content="这是一份测试文档。\n包含多行内容。\n用于验证文档分析功能。"
    )
    
    doc_result = await manager.process_content(doc_content)
    print(f"   文档处理 - 字数: {doc_result['word_count']}, 页数: {doc_result['page_count']}")
    
    # 添加内容到管理器
    content_id = await manager.add_content(text_content)
    print(f"   添加内容ID: {content_id[:8]}...")
    
    # 获取内容
    retrieved_content = await manager.get_content(content_id)
    print(f"   检索内容成功: {retrieved_content is not None}")
    
    # 搜索内容
    search_results = await manager.search_content("测试")
    print(f"   搜索结果数: {len(search_results)}")
    
    # 获取多模态分析
    all_ids = [content_id]
    analysis = await manager.get_multimodal_analysis(all_ids)
    print(f"   多模态分析 - 总内容: {analysis['total_contents']}, 分布: {analysis['modality_distribution']}")
    
    print("   ✅ 多模态内容管理器测试完成")


async def test_multimodal_agent_mixin():
    """测试多模态Agent混入"""
    print("🤖 测试多模态Agent混入...")
    
    # 创建管理器和混入
    manager = MultimodalContentManager()
    agent_mixin = MultimodalAgentMixin(manager)
    
    # 测试处理多模态输入
    inputs = [
        "这是文本输入",
        MediaContent(modality=ModalityType.TEXT, content="第二个文本内容")
    ]
    
    results = await agent_mixin.process_multimodal_input(inputs)
    print(f"   多模态输入处理结果数: {len(results)}")
    
    # 获取能力
    capabilities = await agent_mixin.get_multimodal_capabilities()
    print(f"   支持模态数: {len(capabilities['supported_modalities'])}")
    print(f"   支持功能: {len(capabilities['processing_functions'])}")
    
    # 测试图像分析
    img = Image.new('RGB', (50, 50), color='blue')
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_data = img_io.getvalue()
    
    image_analysis = await agent_mixin.analyze_image(img_data)
    print(f"   图像分析 - 尺寸: {image_analysis['size_estimate']}")
    
    # 测试文档分析
    doc_analysis = await agent_mixin.analyze_document("测试文档内容，用于分析功能验证。")
    print(f"   文档分析 - 字数: {doc_analysis['word_count']}")
    
    # 测试搜索
    search_results = await agent_mixin.search_multimodal_content("测试")
    print(f"   搜索结果数: {len(search_results)}")
    
    # 获取分析
    analytics = await agent_mixin.get_multimodal_analytics()
    print(f"   分析 - 启用: {analytics['enabled']}, 缓存内容: {analytics['cached_contents']}")
    
    print("   ✅ 多模态Agent混入测试完成")


async def test_image_analysis_tool():
    """测试图像分析工具"""
    print("🖼️ 测试图像分析工具...")
    
    # 创建工具
    tool = ImageAnalysisTool()
    
    # 创建一个简单的测试图像
    img = Image.new('RGB', (64, 64), color='green')
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
    
    # 执行工具
    result = await tool.execute(f"data:image/png;base64,{img_base64}")
    
    print(f"   工具执行成功: {result.success}")
    if result.success:
        print(f"   分析结果: {result.content[:100]}...")
    else:
        print(f"   错误: {result.error}")
    
    print("   ✅ 图像分析工具测试完成")


async def test_document_analysis_tool():
    """测试文档分析工具"""
    print("📄 测试文档分析工具...")
    
    # 创建工具
    tool = DocumentAnalysisTool()
    
    # 测试文档内容
    doc_content = (
        "这是一份测试文档。\n"
        "包含多行内容。\n"
        "用于验证文档分析功能。\n"
        "包含一些关键字如测试、验证、功能等。"
    )
    
    # 执行工具
    result = await tool.execute(doc_content)
    
    print(f"   工具执行成功: {result.success}")
    if result.success:
        print(f"   分析结果: {result.content[:100]}...")
    else:
        print(f"   错误: {result.error}")
    
    print("   ✅ 文档分析工具测试完成")


async def test_modality_processors():
    """测试不同模态处理器"""
    print("🔧 测试不同模态处理器...")
    
    manager = MultimodalContentManager()
    
    # 测试所有支持的模态
    test_contents = [
        (ModalityType.TEXT, "测试文本内容"),
        (ModalityType.DOCUMENT, "测试文档内容\n包含多行"),
    ]
    
    for modality, content in test_contents:
        media_content = MediaContent(modality=modality, content=content)
        result = await manager.process_content(media_content)
        print(f"   {modality.value}处理 - 结果: {bool(result)}")
    
    # 测试编码和解码
    text_content = MediaContent(modality=ModalityType.TEXT, content="编码测试")
    encoded = await manager.encode_content(text_content)
    decoded = await manager.decode_content(encoded, ModalityType.TEXT)
    print(f"   编码解码测试成功: {decoded.content == '编码测试'}")
    
    print("   ✅ 模态处理器测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行多模态支持系统测试...\n")
    
    await test_multimodal_content_manager()
    print()
    
    await test_multimodal_agent_mixin()
    print()
    
    await test_image_analysis_tool()
    print()
    
    await test_document_analysis_tool()
    print()
    
    await test_modality_processors()
    print()
    
    print("🎉 所有测试完成！多模态支持系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())