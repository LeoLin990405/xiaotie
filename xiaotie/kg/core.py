"""
知识图谱集成系统

实现知识图谱的构建、存储、查询和推理功能
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict, deque

try:
    import networkx as nx
    from networkx.readwrite import json_graph

    HAS_NETWORKX = True
except ImportError:
    nx = None
    json_graph = None
    HAS_NETWORKX = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from ..schema import Message
from ..memory.core import MemoryManager, MemoryType
from ..context.core import ContextManager, ContextEntity


class NodeType(Enum):
    """节点类型"""
    ENTITY = "entity"           # 实体
    RELATION = "relation"       # 关系
    EVENT = "event"             # 事件
    CONCEPT = "concept"         # 概念
    ATTRIBUTE = "attribute"     # 属性


class RelationType(Enum):
    """关系类型"""
    IS_A = "is_a"               # 继承关系
    PART_OF = "part_of"         # 部分关系
    ASSOCIATION = "association"  # 关联关系
    CAUSE = "cause"             # 因果关系
    TIME = "time"               # 时间关系
    SPACE = "space"             # 空间关系
    ANTONYM = "antonym"         # 反关系
    SYNONYM = "synonym"         # 同义关系


@dataclass
class KGNode:
    """知识图谱节点"""
    id: str
    name: str
    node_type: NodeType
    properties: Dict[str, Any]
    embedding: Optional[List[float]] = None  # 向量嵌入
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.properties is None:
            self.properties = {}


@dataclass
class KGEdge:
    """知识图谱边"""
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: Dict[str, Any]
    weight: float = 1.0  # 关系强度
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.properties is None:
            self.properties = {}


class BaseKnowledgeGraphStore(ABC):
    """知识图谱存储基类"""
    
    @abstractmethod
    async def add_node(self, node: KGNode) -> bool:
        """添加节点"""
        pass
    
    @abstractmethod
    async def add_edge(self, edge: KGEdge) -> bool:
        """添加边"""
        pass
    
    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[KGNode]:
        """获取节点"""
        pass
    
    @abstractmethod
    async def get_neighbors(self, node_id: str, relation_type: Optional[RelationType] = None) -> List[KGNode]:
        """获取邻居节点"""
        pass
    
    @abstractmethod
    async def search_nodes(self, query: str, limit: int = 10) -> List[KGNode]:
        """搜索节点"""
        pass
    
    @abstractmethod
    async def find_path(self, start_node_id: str, end_node_id: str, max_hops: int = 3) -> List[str]:
        """查找路径"""
        pass


class NetworkXKnowledgeGraphStore(BaseKnowledgeGraphStore):
    """基于NetworkX的知识图谱存储"""
    
    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError(
                "networkx is required for NetworkXKnowledgeGraphStore. "
                "Install it with: pip install networkx"
            )
        self.graph = nx.MultiDiGraph()  # 有向多重图（允许多个相同节点间的不同类型边）
        self.node_index: Dict[str, KGNode] = {}  # 节点索引
        self.edge_index: Dict[str, KGEdge] = {}  # 边索引
        self.name_to_id: Dict[str, str] = {}    # 名称到ID的映射
        self.property_index: Dict[str, List[str]] = defaultdict(list)  # 属性索引
    
    async def add_node(self, node: KGNode) -> bool:
        """添加节点"""
        if node.id in self.node_index:
            # 更新现有节点
            self.node_index[node.id] = node
            self.graph.nodes[node.id].update(node.__dict__)
        else:
            # 添加新节点
            self.node_index[node.id] = node
            self.graph.add_node(node.id, **node.__dict__)
        
        # 更新名称索引
        self.name_to_id[node.name.lower()] = node.id
        
        # 更新属性索引
        for prop_name, prop_value in node.properties.items():
            prop_key = f"{prop_name}:{prop_value}"
            if node.id not in self.property_index[prop_key]:
                self.property_index[prop_key].append(node.id)
        
        return True
    
    async def add_edge(self, edge: KGEdge) -> bool:
        """添加边"""
        if edge.id in self.edge_index:
            # 更新现有边
            self.edge_index[edge.id] = edge
            self.graph.edges[edge.source_id, edge.target_id, edge.id].update(edge.__dict__)
        else:
            # 添加新边
            self.edge_index[edge.id] = edge
            self.graph.add_edge(
                edge.source_id, 
                edge.target_id, 
                key=edge.id, 
                **edge.__dict__
            )
        
        return True
    
    async def get_node(self, node_id: str) -> Optional[KGNode]:
        """获取节点"""
        return self.node_index.get(node_id)
    
    async def get_neighbors(self, node_id: str, relation_type: Optional[RelationType] = None) -> List[KGNode]:
        """获取邻居节点"""
        neighbors = []
        
        if node_id not in self.graph:
            return neighbors
        
        # 获取相邻节点
        for neighbor_id in self.graph.successors(node_id):
            neighbor_node = self.node_index.get(neighbor_id)
            if neighbor_node:
                # 如果指定了关系类型，过滤边
                if relation_type:
                    edges = self.graph[node_id][neighbor_id]
                    has_relation = any(
                        self.edge_index[edge_id].relation_type == relation_type 
                        for edge_id in edges
                    )
                    if has_relation:
                        neighbors.append(neighbor_node)
                else:
                    neighbors.append(neighbor_node)
        
        return neighbors
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[KGNode]:
        """搜索节点"""
        results = []
        query_lower = query.lower()
        
        # 按名称匹配
        for node_id, node in self.node_index.items():
            if query_lower in node.name.lower():
                results.append(node)
        
        # 如果结果不足，尝试按属性匹配
        if len(results) < limit:
            for prop_key, node_ids in self.property_index.items():
                if query_lower in prop_key.lower():
                    for node_id in node_ids:
                        node = self.node_index.get(node_id)
                        if node and node not in results:
                            results.append(node)
        
        return results[:limit]
    
    async def find_path(self, start_node_id: str, end_node_id: str, max_hops: int = 3) -> List[str]:
        """查找路径"""
        if not nx.has_path(self.graph, start_node_id, end_node_id):
            return []
        
        try:
            # 使用NetworkX的最短路径算法
            path = nx.shortest_path(self.graph, start_node_id, end_node_id)
            return path if len(path) <= max_hops + 1 else []
        except nx.NetworkXNoPath:
            return []
    
    async def get_subgraph(self, center_node_id: str, radius: int = 2) -> Dict[str, Any]:
        """获取子图"""
        if center_node_id not in self.graph:
            return {"nodes": [], "edges": []}
        
        # 使用ego_graph获取以center为中心的子图
        subgraph = nx.ego_graph(self.graph, center_node_id, radius=radius)
        
        nodes = [self.node_index[node_id] for node_id in subgraph.nodes()]
        edges = []
        
        for u, v, key in subgraph.edges(keys=True):
            edge = self.edge_index.get(key)
            if edge:
                edges.append(edge)
        
        return {
            "center_node": self.node_index[center_node_id],
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
    
    async def get_statistics(self) -> Dict[str, int]:
        """获取图统计信息"""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0,
            "connected_components": nx.number_connected_components(self.graph.to_undirected())
        }
    
    async def serialize(self) -> str:
        """序列化图数据"""
        graph_data = json_graph.node_link_data(self.graph)
        return json.dumps(graph_data)
    
    async def deserialize(self, data: str):
        """反序列化图数据"""
        graph_data = json.loads(data)
        self.graph = json_graph.node_link_graph(graph_data)
        
        # 重建索引
        self.node_index.clear()
        self.edge_index.clear()
        self.name_to_id.clear()
        self.property_index.clear()
        
        for node_id in self.graph.nodes():
            node_attrs = self.graph.nodes[node_id]
            node = KGNode(**{k: v for k, v in node_attrs.items() if k in KGNode.__annotations__})
            self.node_index[node_id] = node
            self.name_to_id[node.name.lower()] = node_id
            for prop_name, prop_value in node.properties.items():
                prop_key = f"{prop_name}:{prop_value}"
                self.property_index[prop_key].append(node_id)
        
        for u, v, key, edge_attrs in self.graph.edges(keys=True, data=True):
            edge = KGEdge(**{k: v for k, v in edge_attrs.items() if k in KGEdge.__annotations__})
            self.edge_index[key] = edge


class KnowledgeGraphBuilder:
    """知识图谱构建器"""
    
    def __init__(self, store: BaseKnowledgeGraphStore):
        self.store = store
        self.entity_extractor = None  # 可以集成实体提取器
    
    async def build_from_text(self, text: str, source_id: str = None) -> Dict[str, Any]:
        """从文本构建知识图谱"""
        import re
        
        # 简化的实体和关系提取
        # 在实际应用中，这里会使用更复杂的NLP技术
        
        entities = []
        relations = []
        
        # 提取可能的实体（简单的名词提取）
        words = re.findall(r'\b\w+\b', text)
        potential_entities = [word for word in set(words) if len(word) > 2 and word[0].isupper() or len(word) > 5]
        
        # 创建实体节点
        created_entities = []
        for i, entity_name in enumerate(potential_entities[:20]):  # 限制实体数量
            entity_id = f"entity_{source_id}_{i}" if source_id else f"entity_{hash(entity_name)}_{i}"
            node = KGNode(
                id=entity_id,
                name=entity_name,
                node_type=NodeType.ENTITY,
                properties={
                    "source": source_id,
                    "extracted_from": text[:50] + "..." if len(text) > 50 else text
                }
            )
            await self.store.add_node(node)
            created_entities.append(node)
        
        # 创建简单的关系（相邻词语之间的关系）
        tokens = text.split()
        created_relations = []
        
        for i in range(len(tokens) - 1):
            token1, token2 = tokens[i], tokens[i+1]
            
            # 查找对应的实体节点
            source_node = next((n for n in created_entities if n.name == token1), None)
            target_node = next((n for n in created_entities if n.name == token2), None)
            
            if source_node and target_node:
                relation_id = f"rel_{hash(source_node.id + target_node.id)}_{i}"
                edge = KGEdge(
                    id=relation_id,
                    source_id=source_node.id,
                    target_id=target_node.id,
                    relation_type=RelationType.ASSOCIATION,
                    properties={
                        "context": f"{token1} -> {token2}",
                        "position": i
                    }
                )
                await self.store.add_edge(edge)
                created_relations.append(edge)
        
        return {
            "entities_created": len(created_entities),
            "relations_created": len(created_relations),
            "source_text_length": len(text)
        }
    
    async def build_from_context(self, context_entities: List[ContextEntity]) -> Dict[str, Any]:
        """从上下文实体构建知识图谱"""
        created_nodes = 0
        created_edges = 0
        
        # 创建实体节点
        for entity in context_entities:
            node_id = f"context_entity_{entity.id}"
            node = KGNode(
                id=node_id,
                name=entity.name,
                node_type=NodeType.ENTITY,
                properties={
                    "entity_type": entity.entity_type,
                    "value": entity.value,
                    "confidence": entity.confidence,
                    "importance": entity.importance
                }
            )
            await self.store.add_node(node)
            created_nodes += 1
        
        # 创建关系（如果实体在同一上下文中出现）
        entity_ids = [f"context_entity_{entity.id}" for entity in context_entities]
        
        for i in range(len(entity_ids) - 1):
            source_id = entity_ids[i]
            target_id = entity_ids[i + 1]
            
            edge_id = f"context_rel_{hash(source_id + target_id)}"
            edge = KGEdge(
                id=edge_id,
                source_id=source_id,
                target_id=target_id,
                relation_type=RelationType.ASSOCIATION,
                properties={
                    "relationship_type": "co_occurrence",
                    "context": "same_context"
                }
            )
            await self.store.add_edge(edge)
            created_edges += 1
        
        return {
            "entities_created": created_nodes,
            "relations_created": created_edges
        }
    
    async def infer_relations(self) -> int:
        """推断隐含关系"""
        # 简单的路径推理：如果A->B且B->C，则可能有A->C
        inferred_count = 0
        
        # 获取所有节点
        all_nodes = list(self.store.node_index.values())
        
        for i, node_a in enumerate(all_nodes):
            neighbors_b = await self.store.get_neighbors(node_a.id)
            
            for node_b in neighbors_b:
                neighbors_c = await self.store.get_neighbors(node_b.id)
                
                for node_c in neighbors_c:
                    # 检查A是否已经有到C的直接连接
                    has_direct = any(
                        edge.target_id == node_c.id 
                        for edge in self.store.edge_index.values() 
                        if edge.source_id == node_a.id
                    )
                    
                    if not has_direct and node_a.id != node_c.id:
                        # 创建间接关系
                        inferred_edge_id = f"inferred_{hash(node_a.id + node_c.id)}"
                        inferred_edge = KGEdge(
                            id=inferred_edge_id,
                            source_id=node_a.id,
                            target_id=node_c.id,
                            relation_type=RelationType.ASSOCIATION,
                            properties={
                                "inferred": True,
                                "path": f"{node_a.name} -> {node_b.name} -> {node_c.name}",
                                "confidence": 0.5  # 推断关系的置信度
                            },
                            weight=0.3  # 推断关系的权重较低
                        )
                        await self.store.add_edge(inferred_edge)
                        inferred_count += 1
        
        return inferred_count


class KnowledgeGraphQueryEngine:
    """知识图谱查询引擎"""
    
    def __init__(self, store: BaseKnowledgeGraphStore):
        self.store = store
    
    async def query_by_type(self, node_type: NodeType, limit: int = 10) -> List[KGNode]:
        """按类型查询节点"""
        results = []
        for node in self.store.node_index.values():
            if node.node_type == node_type:
                results.append(node)
                if len(results) >= limit:
                    break
        return results
    
    async def query_by_property(self, property_name: str, property_value: Any) -> List[KGNode]:
        """按属性查询节点"""
        prop_key = f"{property_name}:{property_value}"
        node_ids = self.store.property_index.get(prop_key, [])
        return [self.store.node_index[node_id] for node_id in node_ids if node_id in self.store.node_index]
    
    async def get_entity_relations(self, entity_name: str) -> Dict[str, List[KGNode]]:
        """获取实体的所有关系"""
        # 首先查找实体
        entity_id = self.store.name_to_id.get(entity_name.lower())
        if not entity_id:
            return {}
        
        incoming_neighbors = []
        outgoing_neighbors = []
        
        # 查找入边邻居（指向此实体的节点）
        for source_id in self.store.graph.predecessors(entity_id):
            source_node = self.store.node_index.get(source_id)
            if source_node:
                incoming_neighbors.append(source_node)
        
        # 查找出边邻居（从此实体指向的节点）
        for target_id in self.store.graph.successors(entity_id):
            target_node = self.store.node_index.get(target_id)
            if target_node:
                outgoing_neighbors.append(target_node)
        
        return {
            "incoming": incoming_neighbors,
            "outgoing": outgoing_neighbors
        }
    
    async def find_related_concepts(self, seed_concept: str, depth: int = 2) -> List[KGNode]:
        """查找相关概念"""
        # 首先查找种子概念
        seed_id = self.store.name_to_id.get(seed_concept.lower())
        if not seed_id:
            return []
        
        # 使用BFS查找相关概念
        related_nodes = []
        visited = {seed_id}
        current_level = [seed_id]
        
        for _ in range(depth):
            next_level = []
            for node_id in current_level:
                # 获取邻居
                neighbors = await self.store.get_neighbors(node_id)
                for neighbor in neighbors:
                    if neighbor.id not in visited:
                        visited.add(neighbor.id)
                        related_nodes.append(neighbor)
                        next_level.append(neighbor.id)
            current_level = next_level
        
        return related_nodes
    
    async def get_central_nodes(self, top_k: int = 10) -> List[Tuple[KGNode, float]]:
        """获取中心节点（使用PageRank算法）"""
        try:
            pagerank_scores = nx.pagerank(self.store.graph)
            
            # 按PageRank分数排序
            sorted_nodes = sorted(
                pagerank_scores.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:top_k]
            
            # 转换为(节点, 分数)格式
            result = []
            for node_id, score in sorted_nodes:
                node = self.store.node_index.get(node_id)
                if node:
                    result.append((node, score))
            
            return result
        except:
            # 如果计算失败，返回空列表
            return []


class KnowledgeGraphManager:
    """知识图谱管理器"""
    
    def __init__(self, 
                 store: BaseKnowledgeGraphStore, 
                 memory_manager: MemoryManager,
                 context_manager: ContextManager):
        self.store = store
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.builder = KnowledgeGraphBuilder(store)
        self.query_engine = KnowledgeGraphQueryEngine(store)
        
        # 图谱统计
        self.stats = {
            "total_nodes": 0,
            "total_edges": 0,
            "last_updated": datetime.now()
        }
    
    async def update_from_message(self, message: Message) -> Dict[str, Any]:
        """从消息更新知识图谱"""
        # 提取上下文实体
        context_frame = await self.context_manager.extract_context(message.content)
        
        # 从上下文构建知识图谱
        build_result = await self.builder.build_from_context(context_frame.entities)
        
        # 更新统计
        stats = await self.store.get_statistics()
        self.stats["total_nodes"] = stats["node_count"]
        self.stats["total_edges"] = stats["edge_count"]
        self.stats["last_updated"] = datetime.now()
        
        # 存储到记忆
        content = f"知识图谱更新: 从消息构建了{build_result['entities_created']}个实体和{build_result['relations_created']}个关系"
        await self.memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.SEMANTIC,
            importance=0.7,
            tags=["knowledge_graph", "update"],
            metadata={
                "message_id": hash(message.content),
                "entities_created": build_result["entities_created"],
                "relations_created": build_result["relations_created"]
            }
        )
        
        return {
            **build_result,
            "graph_stats": stats
        }
    
    async def query_knowledge(self, query: str) -> Dict[str, Any]:
        """查询知识"""
        # 首先在图谱中搜索
        graph_results = await self.query_engine.query_by_property("name", query)
        if not graph_results:
            graph_results = await self.store.search_nodes(query)
        
        # 获取相关概念
        related_concepts = await self.query_engine.find_related_concepts(query)
        
        # 获取中心节点（重要概念）
        central_nodes = await self.query_engine.get_central_nodes(top_k=5)
        
        return {
            "direct_matches": [node.name for node in graph_results],
            "related_concepts": [node.name for node in related_concepts],
            "central_nodes": [(node.name, score) for node, score in central_nodes],
            "match_count": len(graph_results)
        }
    
    async def get_knowledge_subgraph(self, center_entity: str, radius: int = 2) -> Dict[str, Any]:
        """获取知识子图"""
        center_id = self.store.name_to_id.get(center_entity.lower())
        if not center_id:
            return {"error": f"未找到实体: {center_entity}"}
        
        subgraph = await self.store.get_subgraph(center_id, radius)
        
        return {
            "center_entity": subgraph["center_node"].name,
            "nodes": [node.name for node in subgraph["nodes"]],
            "edges": [
                {
                    "source": self.store.node_index[edge.source_id].name,
                    "target": self.store.node_index[edge.target_id].name,
                    "relation": edge.relation_type.value
                }
                for edge in subgraph["edges"]
            ],
            "node_count": subgraph["node_count"],
            "edge_count": subgraph["edge_count"]
        }
    
    async def infer_new_knowledge(self) -> int:
        """推断新知识"""
        inferred_count = await self.builder.infer_relations()
        
        # 更新统计
        stats = await self.store.get_statistics()
        self.stats["total_nodes"] = stats["node_count"]
        self.stats["total_edges"] = stats["edge_count"]
        self.stats["last_updated"] = datetime.now()
        
        return inferred_count
    
    async def get_knowledge_analytics(self) -> Dict[str, Any]:
        """获取知识图谱分析"""
        stats = await self.store.get_statistics()
        central_nodes = await self.query_engine.get_central_nodes(top_k=5)
        
        return {
            "graph_statistics": stats,
            "central_concepts": [(node.name, score) for node, score in central_nodes],
            "last_updated": self.stats["last_updated"].isoformat(),
            "total_nodes": self.stats["total_nodes"],
            "total_edges": self.stats["total_edges"]
        }
    
    async def export_knowledge_graph(self) -> str:
        """导出知识图谱"""
        return await self.store.serialize()
    
    async def import_knowledge_graph(self, data: str):
        """导入知识图谱"""
        await self.store.deserialize(data)
        
        # 更新统计
        stats = await self.store.get_statistics()
        self.stats["total_nodes"] = stats["node_count"]
        self.stats["total_edges"] = stats["edge_count"]
        self.stats["last_updated"] = datetime.now()


class KnowledgeGraphAgentMixin:
    """知识图谱Agent混入类"""
    
    def __init__(self, kg_manager: KnowledgeGraphManager):
        self.kg_manager = kg_manager
        self.kg_enabled = True
    
    async def enable_knowledge_graph(self):
        """启用知识图谱功能"""
        self.kg_enabled = True
    
    async def disable_knowledge_graph(self):
        """禁用知识图谱功能"""
        self.kg_enabled = False
    
    async def update_knowledge_from_context(self, context_text: str) -> Dict[str, Any]:
        """从上下文更新知识"""
        if not self.kg_enabled:
            return {"updated": False, "reason": "知识图谱功能已禁用"}
        
        # 创建一个虚拟消息用于处理
        from ..schema import Message
        message = Message(role="system", content=context_text)
        return await self.kg_manager.update_from_message(message)
    
    async def query_knowledge_base(self, query: str) -> Dict[str, Any]:
        """查询知识库"""
        if not self.kg_enabled:
            return {"results": [], "queried": False}
        
        return await self.kg_manager.query_knowledge(query)
    
    async def get_entity_relationships(self, entity: str) -> Dict[str, Any]:
        """获取实体关系"""
        if not self.kg_enabled:
            return {"relationships": {}, "queried": False}
        
        # 使用查询引擎获取关系
        relations = await self.kg_manager.query_engine.get_entity_relations(entity)
        return {
            "entity": entity,
            "incoming_relations": [node.name for node in relations.get("incoming", [])],
            "outgoing_relations": [node.name for node in relations.get("outgoing", [])],
            "queried": True
        }
    
    async def get_concept_map(self, seed_concept: str, depth: int = 2) -> Dict[str, Any]:
        """获取概念图"""
        if not self.kg_enabled:
            return {"concept_map": {}, "queried": False}
        
        related_nodes = await self.kg_manager.query_engine.find_related_concepts(seed_concept, depth)
        return {
            "seed_concept": seed_concept,
            "related_concepts": [node.name for node in related_nodes],
            "concept_count": len(related_nodes),
            "queried": True
        }
    
    async def infer_new_connections(self) -> int:
        """推断新连接"""
        if not self.kg_enabled:
            return 0
        
        return await self.kg_manager.infer_new_knowledge()
    
    async def get_knowledge_insights(self) -> Dict[str, Any]:
        """获取知识洞察"""
        if not self.kg_enabled:
            return {"analytics": {}, "enabled": False}
        
        analytics = await self.kg_manager.get_knowledge_analytics()
        return {
            "analytics": analytics,
            "enabled": self.kg_enabled
        }
    
    async def export_knowledge(self) -> str:
        """导出知识"""
        if not self.kg_enabled:
            return "{}"
        
        return await self.kg_manager.export_knowledge_graph()
    
    async def import_knowledge(self, data: str):
        """导入知识"""
        if not self.kg_enabled:
            return
        
        await self.kg_manager.import_knowledge_graph(data)
    
    async def get_knowledge_subgraph(self, entity: str, radius: int = 2) -> Dict[str, Any]:
        """获取知识子图"""
        if not self.kg_enabled:
            return {"subgraph": {}, "queried": False}
        
        subgraph = await self.kg_manager.get_knowledge_subgraph(entity, radius)
        return {
            "entity": entity,
            "subgraph": subgraph,
            "queried": True
        }