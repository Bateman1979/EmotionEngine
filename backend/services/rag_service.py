import os
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

class RAGService:
    def __init__(self, knowledge_file=None, model_name=None):
        from backend.config import KNOWLEDGE_BASE_FILE, RAG_EMBEDDING_MODEL
        self.knowledge_file = knowledge_file if knowledge_file else KNOWLEDGE_BASE_FILE
        self.model_name = model_name if model_name else RAG_EMBEDDING_MODEL
        self.model = None
        self.chunks = []
        self.chunk_embeddings = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_knowledge()

    def _load_knowledge(self):
        """Carga el archivo txt, lo divide en párrafos y calcula los embeddings."""
        print("[RAG] Cargando base de conocimiento...")
        if not os.path.exists(self.knowledge_file):
            print(f"[RAG WARN] Archivo no encontrado: {self.knowledge_file}. RAG inactivo.")
            return

        with open(self.knowledge_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Separar por párrafos (doble salto de línea) y limpiar vacíos
        raw_chunks = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        # Ignorar encabezados simples como # Título si no tienen contenido útil
        self.chunks = [chunk for chunk in raw_chunks if len(chunk) > 20]

        if not self.chunks:
            print("[RAG WARN] Base de conocimiento vacía.")
            return

        # Cargar modelo ligero
        print(f"[RAG] Cargando modelo de embedding '{self.model_name}' en {self.device}...")
        self.model = SentenceTransformer(self.model_name, device=self.device)
        
        # Precomputar embeddings
        print(f"[RAG] Vectorizando {len(self.chunks)} fragmentos de texto...")
        with torch.no_grad():
            embeddings = self.model.encode(self.chunks, convert_to_tensor=True, device=self.device)
            # Normalizar para que la similitud de coseno sea solo un producto punto
            self.chunk_embeddings = F.normalize(embeddings, p=2, dim=1)
        
        print("[RAG] ✅ Sistema listo.")

    def search(self, query, top_k=1):
        """Busca el párrafo más relevante para la consulta."""
        if self.model is None or self.chunk_embeddings is None or not self.chunks:
            return "El sistema RAG no está inicializado o la base de conocimiento está vacía."

        with torch.no_grad():
            query_embedding = self.model.encode(query, convert_to_tensor=True, device=self.device)
            query_embedding = F.normalize(query_embedding, p=2, dim=0).unsqueeze(0)
            
            # Calcular similitud del coseno (al estar normalizados es producto punto)
            cosine_scores = torch.mm(query_embedding, self.chunk_embeddings.transpose(0, 1))[0]
            
            # Obtener top_k resultados
            top_results = torch.topk(cosine_scores, k=min(top_k, len(self.chunks)))
            
            best_idx = top_results.indices[0].item()
            best_score = top_results.values[0].item()
            
            # Umbral mínimo de similitud para no devolver basura
            if best_score < 0.2:
                return "No se ha encontrado ninguna recomendación relevante en el manual."
                
            return self.chunks[best_idx]
