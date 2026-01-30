"""
GraphRAG Memory - Long-Term Clinical Memory

Knowledge Graph-based retrieval that captures relationships between:
- User health history
- Dosha assessments over time
- Medications and herbs taken
- Symptom progressions

This replaces flat context windows with relation-aware memory.

For production: Use Neo4j. For development: Use in-memory graph.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import json


class RelationType(str, Enum):
    """Types of relationships in the health knowledge graph."""
    HAS_CONDITION = "HAS_CONDITION"
    TOOK_MEDICATION = "TOOK_MEDICATION"
    TOOK_HERB = "TOOK_HERB"
    HAS_ALLERGY = "HAS_ALLERGY"
    EXPERIENCED_SYMPTOM = "EXPERIENCED_SYMPTOM"
    ASSESSED_AS = "ASSESSED_AS"  # Dosha assessment
    PREVIOUSLY_DISCUSSED = "PREVIOUSLY_DISCUSSED"
    CONTRAINDICATED_WITH = "CONTRAINDICATED_WITH"


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    id: str
    node_type: str  # "User", "Condition", "Herb", "Symptom", "DoshaAssessment"
    properties: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphEdge:
    """A relationship between two nodes."""
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class InMemoryHealthGraph:
    """
    In-memory knowledge graph for user health context.
    
    In production, this would be backed by Neo4j with Cypher queries.
    This implementation provides the same interface for development.
    """
    
    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._user_edges: dict[str, list[GraphEdge]] = {}  # user_id -> edges
    
    def add_node(self, node: GraphNode) -> None:
        """Add or update a node in the graph."""
        self._nodes[node.id] = node
    
    def add_edge(self, edge: GraphEdge) -> None:
        """Add a relationship between nodes."""
        self._edges.append(edge)
        
        # Index by source (assume source is user)
        if edge.source_id not in self._user_edges:
            self._user_edges[edge.source_id] = []
        self._user_edges[edge.source_id].append(edge)
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a node by ID."""
        return self._nodes.get(node_id)
    
    def get_user_context(self, user_id: str, max_items: int = 20) -> list[dict]:
        """
        Retrieve all relevant context for a user.
        
        Returns relationships sorted by recency.
        """
        user_edges = self._user_edges.get(user_id, [])
        
        # Sort by timestamp (most recent first)
        sorted_edges = sorted(user_edges, key=lambda e: e.timestamp, reverse=True)[:max_items]
        
        context = []
        for edge in sorted_edges:
            target_node = self._nodes.get(edge.target_id)
            if target_node:
                context.append({
                    "relation": edge.relation_type.value,
                    "entity_type": target_node.node_type,
                    "entity": target_node.properties,
                    "timestamp": edge.timestamp.isoformat(),
                    "context": edge.properties
                })
        
        return context
    
    def query_relevant_history(
        self, 
        user_id: str, 
        query_keywords: list[str],
        relation_types: Optional[list[RelationType]] = None
    ) -> list[dict]:
        """
        Query graph for context relevant to current query.
        
        Args:
            user_id: User identifier
            query_keywords: Keywords from current query
            relation_types: Filter by specific relation types
            
        Returns:
            Relevant historical context
        """
        user_edges = self._user_edges.get(user_id, [])
        
        results = []
        for edge in user_edges:
            # Filter by relation type if specified
            if relation_types and edge.relation_type not in relation_types:
                continue
            
            target_node = self._nodes.get(edge.target_id)
            if not target_node:
                continue
            
            # Check if any keyword matches node properties
            node_text = json.dumps(target_node.properties).lower()
            if any(kw.lower() in node_text for kw in query_keywords):
                results.append({
                    "relation": edge.relation_type.value,
                    "entity": target_node.properties,
                    "timestamp": edge.timestamp.isoformat(),
                    "relevance": "keyword_match"
                })
        
        return results
    
    def get_medication_history(self, user_id: str) -> list[dict]:
        """Get all medications and herbs the user has taken."""
        return self.query_relevant_history(
            user_id,
            query_keywords=[],  # Get all
            relation_types=[RelationType.TOOK_MEDICATION, RelationType.TOOK_HERB]
        )
    
    def check_historical_interactions(
        self, 
        user_id: str, 
        herb_name: str
    ) -> Optional[dict]:
        """
        Check if user has historical interactions with a herb.
        
        Returns previous experience if found.
        """
        user_edges = self._user_edges.get(user_id, [])
        
        for edge in user_edges:
            if edge.relation_type not in [RelationType.TOOK_HERB, RelationType.TOOK_MEDICATION]:
                continue
            
            target_node = self._nodes.get(edge.target_id)
            if target_node and herb_name.lower() in json.dumps(target_node.properties).lower():
                return {
                    "previously_used": True,
                    "herb": target_node.properties,
                    "when": edge.timestamp.isoformat(),
                    "notes": edge.properties.get("notes", "")
                }
        
        return None


class HealthGraphRAG:
    """
    GraphRAG interface for the Clinical Council.
    
    Combines graph traversal with contextual retrieval.
    """
    
    def __init__(self, graph: Optional[InMemoryHealthGraph] = None):
        self.graph = graph or InMemoryHealthGraph()
    
    def store_dosha_assessment(
        self, 
        user_id: str, 
        dosha_scores: dict,
        assessment_type: str = "prakriti"
    ) -> None:
        """Store a Dosha assessment result."""
        assessment_id = f"dosha_{user_id}_{datetime.now().timestamp()}"
        
        # Create assessment node
        self.graph.add_node(GraphNode(
            id=assessment_id,
            node_type="DoshaAssessment",
            properties={
                "vata": dosha_scores.get("vata", 0),
                "pitta": dosha_scores.get("pitta", 0),
                "kapha": dosha_scores.get("kapha", 0),
                "type": assessment_type,
                "dominant": max(dosha_scores, key=dosha_scores.get)
            }
        ))
        
        # Create user -> assessment edge
        self.graph.add_edge(GraphEdge(
            source_id=user_id,
            target_id=assessment_id,
            relation_type=RelationType.ASSESSED_AS,
            properties={"assessment_type": assessment_type}
        ))
    
    def store_herb_usage(
        self, 
        user_id: str, 
        herb_name: str,
        dosage: Optional[str] = None,
        purpose: Optional[str] = None,
        response: Optional[str] = None
    ) -> None:
        """Store herb usage history."""
        herb_id = f"herb_{herb_name.lower().replace(' ', '_')}"
        
        # Create herb node if not exists
        if not self.graph.get_node(herb_id):
            self.graph.add_node(GraphNode(
                id=herb_id,
                node_type="Herb",
                properties={"name": herb_name}
            ))
        
        # Create usage edge
        self.graph.add_edge(GraphEdge(
            source_id=user_id,
            target_id=herb_id,
            relation_type=RelationType.TOOK_HERB,
            properties={
                "dosage": dosage,
                "purpose": purpose,
                "response": response
            }
        ))
    
    def store_symptom(
        self,
        user_id: str,
        symptom: str,
        severity: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Store a reported symptom."""
        symptom_id = f"symptom_{symptom.lower().replace(' ', '_')}_{datetime.now().timestamp()}"
        
        self.graph.add_node(GraphNode(
            id=symptom_id,
            node_type="Symptom",
            properties={
                "name": symptom,
                "severity": severity,
                "context": context
            }
        ))
        
        self.graph.add_edge(GraphEdge(
            source_id=user_id,
            target_id=symptom_id,
            relation_type=RelationType.EXPERIENCED_SYMPTOM
        ))
    
    def store_condition(
        self,
        user_id: str,
        condition: str,
        diagnosed: bool = False,
        notes: Optional[str] = None
    ) -> None:
        """Store a health condition."""
        condition_id = f"condition_{condition.lower().replace(' ', '_')}"
        
        if not self.graph.get_node(condition_id):
            self.graph.add_node(GraphNode(
                id=condition_id,
                node_type="Condition",
                properties={
                    "name": condition,
                    "diagnosed": diagnosed
                }
            ))
        
        self.graph.add_edge(GraphEdge(
            source_id=user_id,
            target_id=condition_id,
            relation_type=RelationType.HAS_CONDITION,
            properties={"notes": notes}
        ))
    
    def retrieve_context(
        self, 
        user_id: str, 
        query: str,
        include_assessments: bool = True,
        include_medications: bool = True,
        include_symptoms: bool = True
    ) -> str:
        """
        Retrieve relevant context for current query.
        
        Returns formatted string for LLM consumption.
        """
        # Extract keywords from query
        keywords = [w for w in query.lower().split() if len(w) > 3]
        
        context_parts = []
        
        # Get general history
        history = self.graph.get_user_context(user_id, max_items=10)
        
        if history:
            context_parts.append("**Recent Health History:**")
            for item in history[:5]:
                context_parts.append(
                    f"- {item['relation']}: {item['entity']} "
                    f"({item['timestamp'][:10]})"
                )
        
        # Get keyword-specific matches
        relevant = self.graph.query_relevant_history(user_id, keywords)
        if relevant:
            context_parts.append("\n**Potentially Relevant:**")
            for item in relevant[:3]:
                context_parts.append(f"- {item['relation']}: {item['entity']}")
        
        if not context_parts:
            return "No previous health history recorded for this user."
        
        return "\n".join(context_parts)
    
    def check_herb_safety_context(
        self, 
        user_id: str, 
        herb_name: str
    ) -> str:
        """
        Check user's history for herb safety considerations.
        
        Returns warning if relevant history is found.
        """
        # Check if user has taken this herb before
        previous = self.graph.check_historical_interactions(user_id, herb_name)
        if previous:
            return (
                f"📋 **Historical Note:** You've used {herb_name} before "
                f"(around {previous['when'][:10]}). "
                f"Notes: {previous.get('notes', 'No notes recorded.')}"
            )
        
        # Check for conditions that might interact
        conditions = self.graph.query_relevant_history(
            user_id, 
            [herb_name],
            [RelationType.HAS_CONDITION, RelationType.HAS_ALLERGY]
        )
        
        if conditions:
            warnings = [
                f"⚠️ **Caution:** You have {c['entity'].get('name', 'a condition')} "
                "which may interact with this herb."
                for c in conditions
            ]
            return "\n".join(warnings)
        
        return ""


# Singleton instance
_health_graph_rag: Optional[HealthGraphRAG] = None


def get_health_graph_rag() -> HealthGraphRAG:
    """Get or create the HealthGraphRAG instance."""
    global _health_graph_rag
    if _health_graph_rag is None:
        _health_graph_rag = HealthGraphRAG()
    return _health_graph_rag


def init_user_in_graph(user_id: str, health_conditions: list[str] = None) -> None:
    """
    Initialize a user in the knowledge graph.
    
    Call this when a new user starts interacting.
    """
    rag = get_health_graph_rag()
    
    # Create user node
    rag.graph.add_node(GraphNode(
        id=user_id,
        node_type="User",
        properties={"created": datetime.now().isoformat()}
    ))
    
    # Add any known conditions
    for condition in (health_conditions or []):
        rag.store_condition(user_id, condition)
