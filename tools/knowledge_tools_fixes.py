#!/usr/bin/env python3
"""
FIXES for knowledge_tools.py

Lines 46 and 50 have critical bugs:
- Line 46: return knowledge_system.add_entity(entity_type, entity_data)
- Line 50: return knowledge_system.add_relationship(from_entity, to_entity, rel_type)

Both use undefined 'knowledge_system' module instead of _get_knowledge_system() singleton.

FIXED VERSIONS:
"""

def add_knowledge_entity(entity_type, entity_data):
    """
    Add an entity to the knowledge graph

    FIXED: Uses _get_knowledge_system() instead of undefined module
    NOTE: KnowledgeSystem doesn't have add_entity method - needs implementation
    """
    ks = _get_knowledge_system()

    # Store as knowledge entry with entity metadata
    return ks.store_knowledge(
        content=json.dumps(entity_data),
        source=f"entity-{entity_type}",
        source_type="entity",
        metadata={
            "entity_type": entity_type,
            **entity_data
        }
    )


def add_knowledge_relationship(from_entity, to_entity, rel_type):
    """
    Add a relationship between entities

    FIXED: Uses _get_knowledge_system() instead of undefined module
    NOTE: KnowledgeSystem doesn't have add_relationship method - needs implementation
    """
    ks = _get_knowledge_system()

    # Store as knowledge entry with relationship metadata
    relationship_data = {
        "from": from_entity,
        "to": to_entity,
        "type": rel_type
    }

    return ks.store_knowledge(
        content=f"{from_entity} --[{rel_type}]--> {to_entity}",
        source="relationship",
        source_type="relationship",
        metadata=relationship_data
    )


# Alternative: Add methods to KnowledgeSystem class
"""
Add these methods to KnowledgeSystem class in knowledge_system.py:

    def add_entity(self, entity_type: str, entity_data: Dict[str, Any]) -> int:
        '''Add an entity to the knowledge graph'''
        return self.store_knowledge(
            content=json.dumps(entity_data),
            source=f"entity-{entity_type}",
            source_type="entity",
            metadata={
                "entity_type": entity_type,
                **entity_data
            }
        )

    def add_relationship(self, from_entity: str, to_entity: str, rel_type: str) -> int:
        '''Add a relationship between entities'''
        relationship_data = {
            "from": from_entity,
            "to": to_entity,
            "type": rel_type
        }

        return self.store_knowledge(
            content=f"{from_entity} --[{rel_type}]--> {to_entity}",
            source="relationship",
            source_type="relationship",
            metadata=relationship_data
        )
"""
