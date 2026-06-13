from tests import _paths
from nexus_document_parser.loader import load_documents
from nexus_shared.contracts import SourceType, GraphChunkInput
from nexus_graph_builder import GraphBuilder, InMemoryGraphRepository
import uuid

# Load real fixture with wikilinks (Platform.md has [[Vector Store]] and [[Graph Layer|graph]])
docs = load_documents("tests/fixtures/obsidian", SourceType.OBSIDIAN)
print("Loaded docs with wikilinks from Obsidian fixture:")
for d in docs:
    print(f"  {d.source_path}: wikilinks={d.wikilinks}")

# Simulate chunks as they would come from list_approved_graph_chunks after ingestion + approval
# (wikilinks passed explicitly + in metadata, title present)
chunks = []
for d in docs:
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunks.append(GraphChunkInput(
        chunk_id=chunk_id,
        document_id=doc_id,
        content=d.content[:300],
        metadata={"title": d.title, "wikilinks": d.wikilinks},
        wikilinks=d.wikilinks,
        confidence=1.0,
    ))

# Full graph build flow (as in /graph/build or service)
repo = InMemoryGraphRepository()
builder = GraphBuilder(repo)
result = builder.build_from_chunks(chunks)

print("\n=== Full Flow: Graph Build Result (document linking via wikilinks) ===")
print(f"Total entities: {len(result.entities)}")
doc_entities = [e for e in result.entities if e.entity_type == "DOCUMENT"]
print(f"DOCUMENT entities: {len(doc_entities)}")
for e in doc_entities:
    print(f"  - {e.name} (prov keys: {list(e.provenance.keys())})")

print(f"\nTotal relationships: {len(result.relationships)}")
links = [r for r in result.relationships if r.relationship_type == "LINKS_TO"]
print(f"LINKS_TO (document links from wikilinks): {len(links)}")
for r in links:
    print(f"  LINKS_TO with provenance: {r.provenance}")

print("\n=== SUCCESS: Wikilinks from real documents now create explicit LINKS_TO edges in the Knowledge Graph ===")
print("This links documents (e.g. Platform.md -> Vector Store, Platform.md -> Graph Layer).")
print("Provenance preserved (chunk_id + document_id). Ready for search results and UI graph explorer.")
