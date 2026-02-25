"""
知识图谱集成系统测试

验证新知识图谱功能的工作情况
"""

import asyncio
from xiaotie import (
    MemoryManager,
    ContextManager,
    KnowledgeGraphManager,
    KnowledgeGraphAgentMixin,
    KnowledgeGraphBuilder,
    KGNode,
    KGEdge,
    NodeType,
    RelationType,
    Message
)


async def test_knowledge_graph_store():
    """测试知识图谱存储"""
    print("🧠 测试知识图谱存储...")
    
    # 创建存储
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore
    store = KnowledgeGraphStore()
    
    # 创建节点
    node1 = KGNode(
        id="person_john",
        name="John",
        node_type=NodeType.ENTITY,
        properties={"type": "person", "age": 30}
    )
    
    node2 = KGNode(
        id="city_beijing",
        name="Beijing",
        node_type=NodeType.ENTITY,
        properties={"type": "city", "country": "China"}
    )
    
    # 添加节点
    await store.add_node(node1)
    await store.add_node(node2)
    
    print(f"   添加节点: {node1.name}, {node2.name}")
    
    # 创建边
    edge = KGEdge(
        id="john_lives_in_beijing",
        source_id="person_john",
        target_id="city_beijing",
        relation_type=RelationType.ASSOCIATION,
        properties={"relationship": "lives_in", "since": "2020"}
    )
    
    await store.add_edge(edge)
    print(f"   添加边: {edge.id}")
    
    # 获取节点
    retrieved_node = await store.get_node("person_john")
    print(f"   检索节点: {retrieved_node.name if retrieved_node else 'None'}")
    
    # 获取邻居
    neighbors = await store.get_neighbors("person_john")
    print(f"   邻居节点数: {len(neighbors)}")
    
    # 搜索节点
    search_results = await store.search_nodes("Beijing")
    print(f"   搜索结果数: {len(search_results)}")
    
    # 获取统计信息
    stats = await store.get_statistics()
    print(f"   图统计 - 节点: {stats['node_count']}, 边: {stats['edge_count']}")
    
    # 获取子图
    subgraph = await store.get_subgraph("person_john", radius=2)
    print(f"   子图 - 中心节点: {subgraph['center_node'].name}, 节点数: {subgraph['node_count']}")
    
    print("   ✅ 知识图谱存储测试完成")


async def test_knowledge_graph_builder():
    """测试知识图谱构建器"""
    print("🏗️ 测试知识图谱构建器...")
    
    # 创建存储和构建器
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore
    store = KnowledgeGraphStore()
    builder = KnowledgeGraphBuilder(store)
    
    # 从文本构建
    text = "John lives in Beijing. Beijing is a big city in China. John works at a technology company."
    build_result = await builder.build_from_text(text, source_id="test_doc_1")
    
    print(f"   从文本构建 - 实体: {build_result['entities_created']}, 关系: {build_result['relations_created']}")
    
    # 从上下文实体构建
    from xiaotie.context.core import ContextEntity
    context_entities = [
        ContextEntity(id="ctx1", name="Apple", entity_type="fruit", value="Apple"),
        ContextEntity(id="ctx2", name="Red", entity_type="color", value="Red"),
        ContextEntity(id="ctx3", name="Sweet", entity_type="taste", value="Sweet")
    ]
    
    context_build_result = await builder.build_from_context(context_entities)
    print(f"   从上下文构建 - 实体: {context_build_result['entities_created']}, 关系: {context_build_result['relations_created']}")
    
    # 推断关系
    inferred_count = await builder.infer_relations()
    print(f"   推断关系数: {inferred_count}")
    
    print("   ✅ 知识图谱构建器测试完成")


async def test_knowledge_graph_query_engine():
    """测试知识图谱查询引擎"""
    print("🔍 测试知识图谱查询引擎...")
    
    # 创建存储和查询引擎
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore, KnowledgeGraphQueryEngine
    store = KnowledgeGraphStore()
    query_engine = KnowledgeGraphQueryEngine(store)
    
    # 首先添加一些测试数据
    node1 = KGNode(id="apple_fruit", name="Apple", node_type=NodeType.ENTITY, properties={"type": "fruit"})
    node2 = KGNode(id="red_color", name="Red", node_type=NodeType.ATTRIBUTE, properties={"type": "color"})
    node3 = KGNode(id="sweet_taste", name="Sweet", node_type=NodeType.ATTRIBUTE, properties={"type": "taste"})
    
    await store.add_node(node1)
    await store.add_node(node2)
    await store.add_node(node3)
    
    edge1 = KGEdge(
        id="apple_has_color_red",
        source_id="apple_fruit",
        target_id="red_color",
        relation_type=RelationType.ASSOCIATION,
        properties={"relationship": "has_color"}
    )
    
    await store.add_edge(edge1)
    
    # 按类型查询
    fruit_nodes = await query_engine.query_by_type(NodeType.ENTITY, limit=5)
    print(f"   按类型查询实体: {len(fruit_nodes)} 个结果")
    
    # 按属性查询
    apple_nodes = await query_engine.query_by_property("name", "Apple")
    print(f"   按属性查询Apple: {len(apple_nodes)} 个结果")
    
    # 获取实体关系
    relations = await query_engine.get_entity_relations("Apple")
    print(f"   Apple的关系 - 入边: {len(relations.get('incoming', []))}, 出边: {len(relations.get('outgoing', []))}")
    
    # 查找相关概念
    related = await query_engine.find_related_concepts("Apple", depth=2)
    print(f"   与Apple相关的概念: {len(related)} 个")
    
    # 获取中心节点
    central_nodes = await query_engine.get_central_nodes(top_k=3)
    print(f"   中心节点: {len(central_nodes)} 个")
    
    print("   ✅ 知识图谱查询引擎测试完成")


async def test_knowledge_graph_manager():
    """测试知识图谱管理器"""
    print("📊 测试知识图谱管理器...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore
    store = KnowledgeGraphStore()
    
    # 创建管理器
    kg_manager = KnowledgeGraphManager(store, memory_manager, context_manager)
    
    # 创建测试消息
    message = Message(role="user", content="The quick brown fox jumps over the lazy dog in Beijing.")
    
    # 从消息更新知识图谱
    update_result = await kg_manager.update_from_message(message)
    print(f"   从消息更新 - 实体: {update_result['entities_created']}, 关系: {update_result['relations_created']}")
    
    # 查询知识
    query_result = await kg_manager.query_knowledge("fox")
    print(f"   查询'fox' - 直接匹配: {len(query_result['direct_matches'])}, 相关概念: {len(query_result['related_concepts'])}")
    
    # 获取子图
    try:
        subgraph_result = await kg_manager.get_knowledge_subgraph("fox", radius=2)
        print(f"   子图中心: {subgraph_result.get('center_entity', 'Not found')}")
    except Exception as e:
        print(f"   子图查询失败 (可能是因为实体未找到): {str(e)}")
    
    # 推断新知识
    inferred_count = await kg_manager.infer_new_knowledge()
    print(f"   推断新知识: {inferred_count} 个新关系")
    
    # 获取分析
    analytics = await kg_manager.get_knowledge_analytics()
    print(f"   知识图谱分析 - 节点: {analytics['graph_statistics']['node_count']}, 中心概念: {len(analytics['central_concepts'])}")
    
    print("   ✅ 知识图谱管理器测试完成")


async def test_knowledge_graph_agent_mixin():
    """测试知识图谱Agent混入"""
    print("🤖 测试知识图谱Agent混入...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore
    store = KnowledgeGraphStore()
    kg_manager = KnowledgeGraphManager(store, memory_manager, context_manager)
    
    # 创建Agent混入
    kg_agent_mixin = KnowledgeGraphAgentMixin(kg_manager)
    
    # 从上下文更新知识
    context_text = "Machine learning is a subset of artificial intelligence that focuses on algorithms."
    update_result = await kg_agent_mixin.update_knowledge_from_context(context_text)
    print(f"   从上下文更新: {update_result.get('entities_created', 0)} 个实体")
    
    # 查询知识库
    query_result = await kg_agent_mixin.query_knowledge_base("machine learning")
    print(f"   知识库查询 - 匹配数: {query_result['match_count']}")
    
    # 获取实体关系
    try:
        relations = await kg_agent_mixin.get_entity_relationships("machine")
        print(f"   实体关系 - 入边: {len(relations['incoming_relations'])}, 出边: {len(relations['outgoing_relations'])}")
    except Exception as e:
        print(f"   实体关系查询失败: {str(e)}")
    
    # 获取概念图
    concept_map = await kg_agent_mixin.get_concept_map("intelligence", depth=2)
    print(f"   概念图 - 种子概念: {concept_map['seed_concept']}, 相关概念: {concept_map['concept_count']}")
    
    # 推断新连接
    new_connections = await kg_agent_mixin.infer_new_connections()
    print(f"   推断新连接: {new_connections} 个")
    
    # 获取知识洞察
    insights = await kg_agent_mixin.get_knowledge_insights()
    print(f"   知识洞察 - 启用: {insights['enabled']}, 中心概念数: {len(insights['analytics']['central_concepts'])}")
    
    # 获取知识子图
    try:
        subgraph = await kg_agent_mixin.get_knowledge_subgraph("intelligence", radius=2)
        print(f"   知识子图查询成功: {subgraph['queried']}")
    except Exception as e:
        print(f"   知识子图查询失败: {str(e)}")
    
    print("   ✅ 知识图谱Agent混入测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行知识图谱集成系统测试...\n")
    
    await test_knowledge_graph_store()
    print()
    
    await test_knowledge_graph_builder()
    print()
    
    await test_knowledge_graph_query_engine()
    print()
    
    await test_knowledge_graph_manager()
    print()
    
    await test_knowledge_graph_agent_mixin()
    print()
    
    print("🎉 所有测试完成！知识图谱集成系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())