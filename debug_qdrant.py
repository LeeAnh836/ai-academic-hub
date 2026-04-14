import sys
import os
sys.path.append(os.path.abspath('d:/JVB_final/ai-service'))
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v
from core.qdrant import qdrant_manager
results, _ = qdrant_manager.client.scroll(
    collection_name=qdrant_manager.collection_name,
    limit=5,
    with_payload=True,
    with_vectors=False
)
for r in results:
    print(f"Doc ID: {r.payload.get('document_id')}")
    print(f"File: {r.payload.get('file_name')}")
    print(f"Text preview: {repr(r.payload.get('chunk_text', '')[:100])}")
    print("---")
