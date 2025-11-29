from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.runnables import RunnableConfig
import asyncio
import json

from .rag_state import RAGState, QueryRequest, RetrievedChunk, Source
from .vector_store import VectorStore
from .visual_parser import VisualPDFLoader
from .llm_service import LLMService
from .retrieval_service import RetrievalService

class RAGGraph:
    """LangGraph-based RAG orchestration engine"""
    
    def __init__(self, vector_store: VectorStore, pdf_loader: VisualPDFLoader):
        self.vector_store = vector_store
        self.pdf_loader = pdf_loader
        self.llm_service = LLMService()
        self.retrieval_service = RetrievalService(vector_store)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create state graph with RAGState
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("grade_documents", self._grade_documents_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_node("web_search", self._web_search_node)
        workflow.add_node("hallucination_check", self._hallucination_check_node)
        
        # Add edges
        workflow.add_edge("retrieve", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            self._route_after_grade,
            {
                "generate": "generate",
                "web_search": "web_search"
            }
        )
        workflow.add_edge("web_search", "generate")
        workflow.add_edge("generate", "hallucination_check")
        
        # Set entry point
        workflow.set_entry_point("retrieve")
        
        return workflow.compile()
    
    async def _retrieve_node(self, state: RAGState) -> Dict[str, Any]:
        """Retrieve relevant documents from vector store"""
        try:
            # Perform hybrid retrieval
            retrieved_chunks = await self.retrieval_service.retrieve(
                query=state.query,
                top_k=5,
                document_ids=state.documents if state.documents else None
            )
            
            return {
                "retrieved_chunks": retrieved_chunks,
                "scores": [chunk.score for chunk in retrieved_chunks],
                "step": "retrieval"
            }
        except Exception as e:
            return {
                "error": f"Retrieval failed: {str(e)}",
                "step": "error"
            }
    
    async def _grade_documents_node(self, state: RAGState) -> Dict[str, Any]:
        """Grade document relevance and decide next step"""
        if not state.retrieved_chunks:
            return {
                "web_search_needed": True,
                "step": "grading"
            }
        
        try:
            # Grade each retrieved document
            relevant_chunks = []
            for chunk in state.retrieved_chunks:
                grade = await self.llm_service.grade_document_relevance(
                    query=state.query,
                    document_content=chunk.content
                )
                if grade.is_relevant:
                    relevant_chunks.append(chunk)
            
            # If not enough relevant documents, trigger web search
            if len(relevant_chunks) < 2:
                return {
                    "retrieved_chunks": relevant_chunks,
                    "web_search_needed": True,
                    "step": "grading"
                }
            
            return {
                "retrieved_chunks": relevant_chunks,
                "web_search_needed": False,
                "step": "grading"
            }
            
        except Exception as e:
            return {
                "error": f"Document grading failed: {str(e)}",
                "step": "error"
            }
    
    async def _web_search_node(self, state: RAGState) -> Dict[str, Any]:
        """Perform web search to augment knowledge"""
        try:
            # Perform web search
            search_results = await self.llm_service.web_search(state.query)
            
            # Convert search results to chunks
            web_chunks = []
            for result in search_results:
                chunk = RetrievedChunk(
                    id=f"web_{result.url}",
                    content=result.content,
                    page_number=0,
                    doc_id="web_search",
                    chunk_index=0,
                    score=result.relevance_score,
                    metadata={"source": "web", "url": result.url, "title": result.title}
                )
                web_chunks.append(chunk)
            
            # Combine with existing chunks
            all_chunks = state.retrieved_chunks + web_chunks
            
            return {
                "retrieved_chunks": all_chunks,
                "step": "web_search"
            }
            
        except Exception as e:
            return {
                "error": f"Web search failed: {str(e)}",
                "step": "error"
            }
    
    async def _generate_node(self, state: RAGState) -> Dict[str, Any]:
        """Generate answer using retrieved context"""
        try:
            # Build context from retrieved chunks
            context = self._build_context(state.retrieved_chunks)
            
            # Generate answer
            answer = await self.llm_service.generate_answer(
                query=state.query,
                context=context,
                temperature=state.metadata.get("temperature", 0.7)
            )
            
            # Create sources for citation
            sources = []
            for chunk in state.retrieved_chunks[:3]:  # Top 3 sources
                source = Source(
                    chunk_id=chunk.id,
                    content=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    score=chunk.score,
                    document_name=chunk.metadata.get("filename", "Unknown"),
                    page_number=chunk.page_number
                )
                sources.append(source)
            
            return {
                "context": context,
                "answer": answer,
                "sources": sources,
                "step": "generation"
            }
            
        except Exception as e:
            return {
                "error": f"Generation failed: {str(e)}",
                "step": "error"
            }
    
    async def _hallucination_check_node(self, state: RAGState) -> Dict[str, Any]:
        """Check for hallucination in generated answer"""
        try:
            hallucination_score = await self.llm_service.check_hallucination(
                answer=state.answer,
                context=state.context
            )
            
            return {
                "hallucination_score": hallucination_score,
                "step": "complete"
            }
            
        except Exception as e:
            return {
                "error": f"Hallucination check failed: {str(e)}",
                "step": "error"
            }
    
    def _route_after_grade(self, state: RAGState) -> str:
        """Route to next node based on grading results"""
        if state.web_search_needed:
            return "web_search"
        return "generate"
    
    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """Build context string from retrieved chunks"""
        context_parts = []
        for i, chunk in enumerate(chunks[:5]):  # Use top 5 chunks
            context_parts.append(f"[Document {i+1}] {chunk.content}")
        return "\n\n".join(context_parts)
    
    async def process_query(self, request: QueryRequest) -> RAGState:
        """Process a query through the RAG pipeline"""
        # Create initial state
        initial_state = RAGState(
            query=request.query,
            documents=request.document_ids or [],
            metadata={"temperature": request.temperature}
        )
        
        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)
        
        return final_state