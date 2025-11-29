import asyncio
import os
import tempfile
from typing import List, Optional, Dict, Any
from PIL import Image
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import google.generativeai as genai
from langchain.schema import Document as LangchainDocument
import hashlib
import uuid

from .rag_state import DocumentChunk
from .config import settings

class VisualPDFLoader:
    """
    Core innovation: Visual PDF parsing using Gemini Vision
    This is the key differentiator from traditional text-based PDF parsers
    """
    
    def __init__(self):
        # Initialize Gemini Vision
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.vision_model = genai.GenerativeModel('gemini-pro-vision')
        else:
            self.vision_model = None
        
        # Fallback to regular PDF processing
        self.fallback_processor = None
    
    async def process_pdf(self, pdf_path: str, use_vision: bool = True) -> List[DocumentChunk]:
        """
        Process PDF using visual parsing (primary) or fallback to text extraction
        
        Args:
            pdf_path: Path to PDF file
            use_vision: Whether to use vision model (can be disabled for cost reasons)
        
        Returns:
            List of processed document chunks
        """
        try:
            # First, try visual parsing if enabled and model available
            if use_vision and self.vision_model:
                try:
                    return await self._process_pdf_visually(pdf_path)
                except Exception as e:
                    print(f"Visual parsing failed, falling back to text extraction: {e}")
            
            # Fallback to text-based extraction
            return await self._process_pdf_text(pdf_path)
            
        except Exception as e:
            raise Exception(f"PDF processing failed: {str(e)}")
    
    async def _process_pdf_visually(self, pdf_path: str) -> List[DocumentChunk]:
        """
        Process PDF using visual parsing - the core innovation
        
        1. Convert PDF pages to high-resolution images
        2. Use Gemini Vision to extract structured content
        3. Apply layout analysis and table detection
        4. Generate structured markdown output
        """
        chunks = []
        
        # Convert PDF to images
        images = await self._pdf_to_images(pdf_path)
        
        for page_num, image in enumerate(images, start=1):
            try:
                # Analyze page layout and detect elements
                page_elements = await self._analyze_page_layout(image, page_num)
                
                # Process each element type
                for element in page_elements:
                    if element["type"] == "table":
                        # Process table with special handling
                        table_chunks = await self._process_table_element(
                            element["image"], page_num, element["bbox"]
                        )
                        chunks.extend(table_chunks)
                    elif element["type"] == "text":
                        # Process regular text
                        text_chunk = await self._process_text_element(
                            element["image"], page_num, element["bbox"]
                        )
                        if text_chunk:
                            chunks.append(text_chunk)
                    elif element["type"] == "figure":
                        # Process figures and diagrams
                        figure_chunk = await self._process_figure_element(
                            element["image"], page_num, element["bbox"]
                        )
                        if figure_chunk:
                            chunks.append(figure_chunk)
                
            except Exception as e:
                print(f"Error processing page {page_num}: {e}")
                # Fallback: process entire page as text
                fallback_chunk = await self._process_entire_page(image, page_num)
                if fallback_chunk:
                    chunks.append(fallback_chunk)
        
        # Apply intelligent chunking strategy
        return self._apply_chunking_strategy(chunks)
    
    async def _pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[Image.Image]:
        """Convert PDF to high-resolution images"""
        # Use pdf2image for better quality
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt='png',
            thread_count=4,
            use_pdftocairo=True
        )
        return images
    
    async def _analyze_page_layout(self, image: Image.Image, page_num: int) -> List[Dict[str, Any]]:
        """
        Analyze page layout to detect different element types
        
        Uses a lightweight approach with Gemini Vision to identify:
        - Tables
        - Figures
        - Headers/Footers
        - Main text blocks
        """
        prompt = f"""
        Analyze this PDF page and identify different content regions.
        
        Please identify and describe:
        1. Tables (with their approximate bounding boxes)
        2. Figures/diagrams (with their approximate bounding boxes)
        3. Headers and footers (to be excluded)
        4. Main text blocks
        
        Return the response in this JSON format:
        {{
            "elements": [
                {{
                    "type": "table|figure|text",
                    "bbox": [x1, y1, x2, y2],
                    "description": "brief description"
                }}
            ]
        }}
        """
        
        try:
            response = self.vision_model.generate_content([prompt, image])
            layout_data = json.loads(response.text)
            return layout_data.get("elements", [])
        except Exception as e:
            print(f"Layout analysis failed for page {page_num}: {e}")
            # Fallback: treat entire page as text
            return [{
                "type": "text",
                "bbox": [0, 0, image.width, image.height],
                "description": "Full page text"
            }]
    
    async def _process_table_element(self, image: Image.Image, page_num: int, bbox: List[int]) -> List[DocumentChunk]:
        """Process table element with special handling for structured data"""
        # Crop to table region
        table_image = image.crop(bbox)
        
        prompt = """
        Convert this table image to structured markdown format.
        
        Requirements:
        1. Preserve all numerical values exactly as shown
        2. Maintain table structure with proper markdown syntax
        3. Handle merged cells appropriately
        4. Include column headers if present
        5. Ensure data accuracy for financial/technical tables
        
        Return only the markdown table, no additional text.
        """
        
        try:
            response = self.vision_model.generate_content([prompt, table_image])
            table_markdown = response.text.strip()
            
            # Create chunk for the table
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                content=table_markdown,
                page_number=page_num,
                doc_id=f"table_page_{page_num}",
                chunk_index=0,
                metadata={
                    "type": "table",
                    "bbox": bbox,
                    "processing_method": "vision",
                    "confidence": 0.95
                }
            )
            
            return [chunk]
            
        except Exception as e:
            print(f"Table processing failed: {e}")
            return []
    
    async def _process_text_element(self, image: Image.Image, page_num: int, bbox: List[int]) -> Optional[DocumentChunk]:
        """Process regular text element"""
        # Crop to text region
        text_image = image.crop(bbox)
        
        prompt = """
        Extract the text content from this image.
        
        Requirements:
        1. Preserve the exact text content
        2. Maintain proper formatting and structure
        3. Handle multi-column text appropriately
        4. Include any important formatting (bold, italic, etc.)
        
        Return only the extracted text, no additional commentary.
        """
        
        try:
            response = self.vision_model.generate_content([prompt, text_image])
            extracted_text = response.text.strip()
            
            if not extracted_text:
                return None
            
            return DocumentChunk(
                id=str(uuid.uuid4()),
                content=extracted_text,
                page_number=page_num,
                doc_id=f"text_page_{page_num}",
                chunk_index=0,
                metadata={
                    "type": "text",
                    "bbox": bbox,
                    "processing_method": "vision",
                    "confidence": 0.90
                }
            )
            
        except Exception as e:
            print(f"Text processing failed: {e}")
            return None
    
    async def _process_figure_element(self, image: Image.Image, page_num: int, bbox: List[int]) -> Optional[DocumentChunk]:
        """Process figure/diagram element"""
        # Crop to figure region
        figure_image = image.crop(bbox)
        
        prompt = """
        Describe this figure/diagram in detail.
        
        Requirements:
        1. Provide a comprehensive description of what the figure shows
        2. Identify key elements, trends, or patterns
        3. Explain any data visualizations (charts, graphs, etc.)
        4. Include relevant technical details
        5. Make the description searchable and useful for RAG
        
        Return a detailed text description that captures the essence of the figure.
        """
        
        try:
            response = self.vision_model.generate_content([prompt, figure_image])
            description = response.text.strip()
            
            if not description:
                return None
            
            return DocumentChunk(
                id=str(uuid.uuid4()),
                content=f"Figure Description: {description}",
                page_number=page_num,
                doc_id=f"figure_page_{page_num}",
                chunk_index=0,
                metadata={
                    "type": "figure",
                    "bbox": bbox,
                    "processing_method": "vision",
                    "confidence": 0.85,
                    "has_image": True
                }
            )
            
        except Exception as e:
            print(f"Figure processing failed: {e}")
            return None
    
    async def _process_entire_page(self, image: Image.Image, page_num: int) -> Optional[DocumentChunk]:
        """Fallback: process entire page as text"""
        prompt = """
        Extract all text content from this PDF page.
        
        Requirements:
        1. Extract all readable text
        2. Maintain logical reading order
        3. Preserve table structures if present
        4. Handle multiple columns appropriately
        
        Return the extracted text content.
        """
        
        try:
            response = self.vision_model.generate_content([prompt, image])
            content = response.text.strip()
            
            if not content:
                return None
            
            return DocumentChunk(
                id=str(uuid.uuid4()),
                content=content,
                page_number=page_num,
                doc_id=f"page_{page_num}",
                chunk_index=0,
                metadata={
                    "type": "full_page",
                    "processing_method": "vision_fallback",
                    "confidence": 0.70
                }
            )
            
        except Exception as e:
            print(f"Entire page processing failed: {e}")
            return None
    
    async def _process_pdf_text(self, pdf_path: str) -> List[DocumentChunk]:
        """Fallback text-based PDF processing using PyMuPDF"""
        chunks = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(1, doc.page_count + 1):
                page = doc.load_page(page_num - 1)
                text = page.get_text()
                
                if text.strip():
                    chunk = DocumentChunk(
                        id=str(uuid.uuid4()),
                        content=text.strip(),
                        page_number=page_num,
                        doc_id=f"text_page_{page_num}",
                        chunk_index=0,
                        metadata={
                            "type": "text",
                            "processing_method": "text_extraction",
                            "confidence": 0.60
                        }
                    )
                    chunks.append(chunk)
            
            doc.close()
            
        except Exception as e:
            print(f"Text extraction failed: {e}")
            raise
        
        return chunks
    
    def _apply_chunking_strategy(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Apply intelligent chunking strategy based on content type and size
        
        - Keep tables as single chunks (they're already well-structured)
        - Split large text blocks using semantic boundaries
        - Maintain context with overlapping chunks
        """
        final_chunks = []
        
        for chunk in chunks:
            if chunk.metadata.get("type") == "table":
                # Keep tables as single chunks
                final_chunks.append(chunk)
            else:
                # Apply text chunking with overlap
                text_chunks = self._split_text_semantically(
                    chunk.content,
                    chunk_size=settings.chunk_size,
                    overlap=settings.chunk_overlap
                )
                
                for i, text_chunk in enumerate(text_chunks):
                    new_chunk = DocumentChunk(
                        id=f"{chunk.id}_{i}",
                        content=text_chunk,
                        page_number=chunk.page_number,
                        doc_id=chunk.doc_id,
                        chunk_index=i,
                        metadata={**chunk.metadata, "chunk_index": i}
                    )
                    final_chunks.append(new_chunk)
        
        return final_chunks
    
    def _split_text_semantically(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into semantically meaningful chunks"""
        # Simple implementation - can be enhanced with more sophisticated NLP
        words = text.split()
        chunks = []
        
        if len(words) <= chunk_size:
            return [text]
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)
            
            # Move forward with overlap
            i += chunk_size - overlap
        
        return chunks
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        return hashlib.md5(content.encode()).hexdigest()