from typing import Optional, Dict, Any, List
import asyncio
import httpx
from dataclasses import dataclass
import json

from .config import settings

@dataclass
class SearchResult:
    """Web search result"""
    title: str
    url: str
    content: str
    relevance_score: float

@dataclass
class DocumentGrade:
    """Document relevance grade"""
    is_relevant: bool
    confidence: float
    reasoning: str

class LLMService:
    """LLM service for generation, grading, and web search"""
    
    def __init__(self):
        self.gemini_api_key = settings.gemini_api_key
        self.openai_api_key = settings.openai_api_key
        self.tavily_api_key = settings.tavily_api_key
        self.serper_api_key = settings.serper_api_key
    
    async def generate_answer(
        self, 
        query: str, 
        context: str, 
        temperature: float = 0.7,
        model: str = "gemini"
    ) -> str:
        """Generate answer using retrieved context"""
        try:
            if model == "gemini" and self.gemini_api_key:
                return await self._generate_with_gemini(query, context, temperature)
            elif model == "openai" and self.openai_api_key:
                return await self._generate_with_openai(query, context, temperature)
            else:
                # Fallback to simple template-based generation
                return self._generate_with_template(query, context)
                
        except Exception as e:
            raise Exception(f"Answer generation failed: {str(e)}")
    
    async def _generate_with_gemini(self, query: str, context: str, temperature: float) -> str:
        """Generate answer using Gemini"""
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Based on the following context, please answer the user's question.
        
        Context:
        {context}
        
        Question: {query}
        
        Instructions:
        1. Answer directly and concisely
        2. Use only information from the provided context
        3. If the context doesn't contain enough information, say so
        4. Cite relevant sources when possible
        5. Maintain a helpful and professional tone
        
        Answer:
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    async def _generate_with_openai(self, query: str, context: str, temperature: float) -> str:
        """Generate answer using OpenAI"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that answers questions based on provided context."
                        },
                        {
                            "role": "user",
                            "content": f"Context: {context}\n\nQuestion: {query}"
                        }
                    ],
                    "temperature": temperature,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"OpenAI API error: {response.text}")
    
    def _generate_with_template(self, query: str, context: str) -> str:
        """Fallback template-based generation"""
        # Simple extraction-based approach
        sentences = context.split('.')
        relevant_sentences = []
        
        query_words = query.lower().split()
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            relevance_score = sum(1 for word in query_words if word in sentence_lower)
            
            if relevance_score > 0:
                relevant_sentences.append((sentence.strip(), relevance_score))
        
        # Sort by relevance and take top sentences
        relevant_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [sent for sent, _ in relevant_sentences[:3]]
        
        if top_sentences:
            answer = f"Based on the provided context: {' '.join(top_sentences)}"
            if len(top_sentences) > 1:
                answer += " These sentences seem most relevant to your question."
        else:
            answer = "I couldn't find relevant information in the provided context to answer your question."
        
        return answer
    
    async def grade_document_relevance(
        self, 
        query: str, 
        document_content: str
    ) -> DocumentGrade:
        """Grade document relevance to query"""
        try:
            if self.gemini_api_key:
                return await self._grade_with_gemini(query, document_content)
            else:
                return self._grade_with_heuristics(query, document_content)
                
        except Exception as e:
            print(f"Document grading failed: {e}")
            # Fallback: assume relevant
            return DocumentGrade(is_relevant=True, confidence=0.5, reasoning="Grading failed, assuming relevant")
    
    async def _grade_with_gemini(self, query: str, document_content: str) -> DocumentGrade:
        """Grade document relevance using Gemini"""
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Evaluate if the following document content is relevant to answer the user's query.
        
        Query: {query}
        
        Document Content: {document_content[:1000]}...
        
        Instructions:
        1. Determine if this document contains information that could help answer the query
        2. Consider both direct relevance and contextual relevance
        3. Provide a confidence score (0.0 to 1.0)
        4. Explain your reasoning
        
        Return your response in this JSON format:
        {{
            "is_relevant": true/false,
            "confidence": 0.8,
            "reasoning": "This document is relevant because..."
        }}
        """
        
        response = model.generate_content(prompt)
        
        try:
            result = json.loads(response.text)
            return DocumentGrade(
                is_relevant=result.get("is_relevant", False),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", "No reasoning provided")
            )
        except json.JSONDecodeError:
            # Fallback: parse from text
            text = response.text.lower()
            is_relevant = "relevant" in text and "not relevant" not in text
            confidence = 0.6 if is_relevant else 0.4
            
            return DocumentGrade(
                is_relevant=is_relevant,
                confidence=confidence,
                reasoning="Parsed from text response"
            )
    
    def _grade_with_heuristics(self, query: str, document_content: str) -> DocumentGrade:
        """Simple heuristic-based grading"""
        query_words = set(query.lower().split())
        content_words = set(document_content.lower().split())
        
        # Calculate overlap
        overlap = len(query_words & content_words)
        total_query_words = len(query_words)
        
        # Calculate relevance score
        if total_query_words == 0:
            relevance_score = 0
        else:
            relevance_score = overlap / total_query_words
        
        # Determine relevance based on threshold
        is_relevant = relevance_score > 0.3  # 30% overlap threshold
        confidence = min(relevance_score * 2, 1.0)  # Scale confidence
        
        reasoning = f"Query-document word overlap: {overlap}/{total_query_words} ({relevance_score:.2%})"
        
        return DocumentGrade(
            is_relevant=is_relevant,
            confidence=confidence,
            reasoning=reasoning
        )
    
    async def check_hallucination(self, answer: str, context: str) -> float:
        """Check if answer contains hallucinations (information not in context)"""
        try:
            if self.gemini_api_key:
                return await self._check_hallucination_with_gemini(answer, context)
            else:
                return self._check_hallucination_heuristic(answer, context)
                
        except Exception as e:
            print(f"Hallucination check failed: {e}")
            return 0.5  # Neutral score on failure
    
    async def _check_hallucination_with_gemini(self, answer: str, context: str) -> float:
        """Check hallucination using Gemini"""
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Analyze if the following answer contains information that is not supported by the provided context.
        
        Context: {context}
        
        Answer: {answer}
        
        Instructions:
        1. Identify any claims or facts in the answer
        2. Check if each claim is supported by the context
        3. Calculate a hallucination score (0.0 = no hallucination, 1.0 = complete hallucination)
        4. Focus on factual accuracy, not phrasing differences
        
        Return only the hallucination score as a number between 0.0 and 1.0.
        """
        
        response = model.generate_content(prompt)
        
        try:
            # Try to parse as float
            score = float(response.text.strip())
            return max(0.0, min(1.0, score))  # Clamp to valid range
        except ValueError:
            # Fallback: parse from text
            text = response.text.lower()
            if "no hallucination" in text or "supported" in text:
                return 0.1
            elif "some hallucination" in text or "partial" in text:
                return 0.5
            elif "hallucination" in text:
                return 0.8
            else:
                return 0.3  # Uncertain
    
    def _check_hallucination_heuristic(self, answer: str, context: str) -> float:
        """Simple heuristic-based hallucination check"""
        # Extract key entities from answer
        answer_words = set(answer.lower().split())
        context_words = set(context.lower().split())
        
        # Calculate coverage
        if not answer_words:
            return 0.0
        
        coverage = len(answer_words & context_words) / len(answer_words)
        
        # Invert coverage to get hallucination score
        # High coverage = low hallucination
        hallucination_score = max(0.0, 1.0 - coverage)
        
        return hallucination_score
    
    async def web_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Perform web search to augment knowledge"""
        try:
            if self.tavily_api_key:
                return await self._search_with_tavily(query, max_results)
            elif self.serper_api_key:
                return await self._search_with_serper(query, max_results)
            else:
                return []  # No search API available
                
        except Exception as e:
            print(f"Web search failed: {e}")
            return []
    
    async def _search_with_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Tavily API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                    "include_raw_content": True
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for result in data.get("results", []):
                    search_result = SearchResult(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        content=result.get("raw_content", result.get("content", "")),
                        relevance_score=result.get("score", 0.5)
                    )
                    results.append(search_result)
                
                return results
            else:
                raise Exception(f"Tavily API error: {response.text}")
    
    async def _search_with_serper(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Serper API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "num": max_results
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for result in data.get("organic", []):
                    search_result = SearchResult(
                        title=result.get("title", ""),
                        url=result.get("link", ""),
                        content=result.get("snippet", ""),
                        relevance_score=0.5  # Default score
                    )
                    results.append(search_result)
                
                return results
            else:
                raise Exception(f"Serper API error: {response.text}")
    
    async def get_llm_stats(self) -> Dict[str, Any]:
        """Get LLM service statistics"""
        return {
            "service": "llm",
            "gemini_available": bool(self.gemini_api_key),
            "openai_available": bool(self.openai_api_key),
            "tavily_available": bool(self.tavily_api_key),
            "serper_available": bool(self.serper_api_key)
        }