"""
Academic Paper Generator

Generates academic papers in LaTeX format from structured JSON data using
language models to create content for each section.
"""

import json
import subprocess
import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import statements would be here in a real application
from prompt.template import PAPER_CHAPTER_PROMPT, PAPER_CHAPTER_WITH_PRECEDING_PROMPT, PAPER_INFO_PROMPT, PAPER_NOTATION_PROMPT
from llm.llm import LLM
from utils.utils import parse_llm_output_to_json

# --------------------------------
# Data Models
# --------------------------------

@dataclass
class Chapter:
    """Represents a chapter in the paper with its hierarchical structure and content."""
    path: List[str]  # Hierarchical path (e.g., ["Problem Analysis", "Task 1 Analysis"])
    content: str = ""
    title: str = ""
    is_generated: bool = False
    needs_content: bool = False
    
    @property
    def path_string(self) -> str:
        """Returns the full path as a string (e.g., 'Problem Analysis > Task 1 Analysis')"""
        return " > ".join(self.path)
    
    @property
    def depth(self) -> int:
        """Returns the heading level (depth in hierarchy)"""
        return len(self.path)
    
    @property
    def display_title(self) -> str:
        """Returns the chapter title to display (custom title or last path element)"""
        return self.title if self.title else self.path[-1]

# --------------------------------
# Language Model Interface
# --------------------------------

def escape_underscores_in_quotes(text):
    pattern = r'(".*?")|(\'.*?\')'
    def replace_underscores(match):
        content = match.group(0)[1:-1]
        escaped_content = content.replace('_', r'\_')
        return f'"{escaped_content}"' if match.group(0).startswith('"') else f"'{escaped_content}'"
    
    result = re.sub(pattern, replace_underscores, text, flags=re.DOTALL)
    return result


class ContentGenerator:
    """Interface for generating content using language models"""
    
    def __init__(self, llm):
        self.llm = llm
    
    def generate_chapter_content(self, prompt: str) -> Dict[str, str]:
        """Generate chapter content using the language model"""
        response = self.llm.generate(prompt)
        response = escape_underscores_in_quotes(response)
        response = response.replace("```latex", "").replace("```", "")
        # return self._parse_latex_response(response)
        return response
    
    def _parse_latex_response(self, latex_string: str) -> Dict[str, str]:
        """Parse LLM response from LaTeX format"""
        pattern = r"```latex\s*\\chapter{\s*(.*?)\s*}\s*(.*)```"
        match = re.match(pattern, latex_string.strip(), re.DOTALL)
        
        if match:
            return {
                "title": match.group(1).strip(),
                "content": match.group(2).strip()
            }
        
        # Fallback if format doesn't match
        return {
            "title": "",
            "content": latex_string
        }

# --------------------------------
# Paper Structure
# --------------------------------

class OutlineGenerator:
    """Creates the hierarchical structure of the paper"""
    
    def create_outline(self, task_count: int) -> List[Chapter]:
        """Create a complete chapter structure based on number of tasks"""
        print(f"Creating paper outline for {task_count} tasks")
        
        # Define the structure template
        outline = self._create_base_outline(task_count)
        
        # Create chapter objects
        chapters = []
        for path in outline:
            # A chapter needs content if it's a leaf node (has no children)
            needs_content = not any(other[:len(path)] == path and len(other) > len(path) 
                                   for other in outline)
            chapters.append(Chapter(path=path, needs_content=needs_content))
        
        content_chapters = sum(1 for c in chapters if c.needs_content)
        print(f"Created {len(chapters)} sections, {content_chapters} require content generation")
        for chapter in chapters:
            print(chapter.path_string)
        return chapters
    
    def _create_base_outline(self, task_count: int) -> List[List[str]]:
        """Define the hierarchical structure of the paper"""
        # Define the template structure
        outline = [
            ["Problem Restatement", "Problem Background"],
            ["Problem Restatement", "Problem Statement"],
            ["Model Assumptions"],
            ["Explanation of Assumptions"],
            ["Problem Analysis"]
        ]
        
        # Add task-specific analysis chapters
        for i in range(1, task_count + 1):
            outline.append(["Problem Analysis", f"Task {i} Analysis"])
        
        outline.append(["Solution to the Problem"])
        
        # Add task-specific solution chapters
        for i in range(1, task_count + 1):
            outline.append(["Solution to the Problem", f"Task {i} Solution", "Model Setup: Assumptions and Chain Models"])
            outline.append(["Solution to the Problem", f"Task {i} Solution", "Model Calculation"])
        
        # Add conclusion and reference sections
        outline.extend([
            ["Model Conclusion", "Model Advantages"],
            ["Model Conclusion", "Model Limitations"],
            ["Notation and Explanations"]  
        ])
        
        return outline

    def generate_chapter_relevance_map(self, task_count: int) -> Dict[str, List[str]]:
        """
        Dynamically generate chapter relevance mapping based on the number of tasks.
        
        Args:
            task_count: Number of tasks in the paper
            
        Returns:
            Dictionary mapping chapter paths to lists of related chapter paths
        """
        relevance_map = {}

        for i in range(1, task_count + 1):
            setup_path = f"Solution to the Problem > Task {i} Solution > Model Setup: Assumptions and Chain Models"
            relevance_map[setup_path] = [f"Problem Analysis > Task {i} Analysis"]

        for i in range(1, task_count + 1):
            calculation_path = f"Solution to the Problem > Task {i} Solution > Model Calculation"
            relevance_map[calculation_path] = [
                f"Problem Analysis > Task {i} Analysis",
                f"Solution to the Problem > Task {i} Solution > Model Setup: Assumptions and Chain Models",
            ]
        
        # Model conclusion chapters should include all task solutions
        task_solutions = []
        for i in range(1, task_count + 1):
            task_solutions += [
                f"Solution to the Problem > Task {i} Solution > Model Calculation",
                f"Solution to the Problem > Task {i} Solution > Model Setup: Assumptions and Chain Models"
            ]
        
        relevance_map["Model Conclusion > Model Advantages"] = task_solutions.copy()
        relevance_map["Model Conclusion > Model Limitations"] = task_solutions.copy()
        relevance_map["Notation and Explanations"] = task_solutions.copy()
        
        return relevance_map


# --------------------------------
# Context Extraction
# --------------------------------

class ContextExtractor:
    """Extracts relevant data from JSON for each chapter"""
    
    def get_context_for_chapter(self, chapter: Chapter, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant JSON data for a specific chapter"""
        path = chapter.path
        
        # Handle different chapter types
        if path == ["Problem Restatement", "Problem Background"]:
            return {"problem_background": data.get("problem_background", "")}
            
        elif path == ["Problem Restatement", "Problem Statement"]:
            return {"problem_requirement": data.get("problem_requirement", "")}
            
        elif path == ["Model Assumptions"]:
            return self._get_assumptions_context(data)
    
        elif path == ["Explanation of Assumptions"]:
            return {}
            
        elif self._is_task_analysis(path):
            return self._get_task_analysis_context(path, data)
            
        elif self._is_model_setup(path):
            return self._get_model_setup_context(path, data)
            
        elif self._is_model_calculation(path):
            return self._get_model_calculation_context(path, data)
            
        # Default empty context for other sections
        return {}
    
    def _get_assumptions_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context for assumptions sections"""
        context = {"problem_analysis": data.get("problem_analysis", "")}
        
        # Extract task modeling information
        keys = ['task_description', 'task_analysis', 'mathematical_modeling_process']
        context["tasks"] = [
            {k: v for k, v in task.items() if k in keys}
            for task in data['tasks']
        ]
        
        return context
    
    def _get_task_analysis_context(self, path: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context for task analysis sections"""
        task_num = self._extract_task_number(path[1])
        if not self._is_valid_task_index(task_num, data):
            return {}
            
        task_data = data["tasks"][task_num]
        keys = ['task_analysis', 'task_description']
        return {
            f'task_{task_num+1}': {
                k: v for k, v in task_data.items() if k in keys
            }
        }
    
    def _get_model_setup_context(self, path: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context for model setup sections"""
        task_num = self._extract_task_number(path[1])
        if not self._is_valid_task_index(task_num, data):
            return {}
            
        task_data = data["tasks"][task_num]
        keys = ['preliminary_formulas', 'mathematical_modeling_process']
        return {
            f'task_{task_num+1}': {
                k: task_data.get(k, "") for k in keys
            }
        }
    
    def _get_model_calculation_context(self, path: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context for model calculation sections"""
        task_num = self._extract_task_number(path[1])
        if not self._is_valid_task_index(task_num, data):
            return {}
            
        task_data = data["tasks"][task_num]
        keys = ['mathematical_modeling_process', 'execution_result', 'solution_interpretation', 'subtask_outcome_analysis']
        return {
            f'task_{task_num+1}': {
                k: task_data.get(k, "") for k in keys
            }
        }
    
    def _is_task_analysis(self, path: List[str]) -> bool:
        """Check if path is a task analysis section"""
        return (len(path) == 2 and 
                path[0] == "Problem Analysis" and 
                path[1].startswith("Task "))
    
    def _is_model_setup(self, path: List[str]) -> bool:
        """Check if path is a model setup section"""
        return (len(path) == 3 and 
                path[0] == "Solution to the Problem" and 
                path[1].startswith("Task ") and 
                path[2] == "Model Setup: Assumptions and Chain Models")
    
    def _is_model_calculation(self, path: List[str]) -> bool:
        """Check if path is a model calculation section"""
        return (len(path) == 3 and 
                path[0] == "Solution to the Problem" and 
                path[1].startswith("Task ") and 
                path[2] == "Model Calculation")
    
    def _extract_task_number(self, task_string: str) -> int:
        """Extract task number from strings like 'Task 1 Analysis'"""
        try:
            return int(task_string.split()[1]) - 1  # Convert to 0-indexed
        except (IndexError, ValueError):
            return -1
    
    def _is_valid_task_index(self, index: int, data: Dict[str, Any]) -> bool:
        """Check if the task index is valid"""
        return 0 <= index < len(data.get("tasks", []))

# --------------------------------
# Prompt Creation
# --------------------------------

class PromptCreator:
    """Creates prompts for the language model"""
    
    def __init__(self):
        pass
    
    def create_prompt(self, 
                     chapter: Chapter, 
                     context: Dict[str, Any], 
                     previous_chapters: List[Chapter]) -> str:
        """Create a prompt for generating chapter content"""
        # Format JSON context
        json_str = json.dumps(context, indent=2)
        
        # Format previous chapters
        previous_text = self._format_previous_chapters(previous_chapters)
        
        if chapter.path == ["Notation and Explanations"]:
            return PAPER_NOTATION_PROMPT.format(
                previous_chapters=previous_text,
            )
        else:
            if json_str == '{}':
                return PAPER_CHAPTER_WITH_PRECEDING_PROMPT.format(
                    chapter_path=chapter.path_string,
                    previous_chapters=previous_text
                )
            else:
                # Build the prompt using the template
                return PAPER_CHAPTER_PROMPT.format(
                    chapter_path=chapter.path_string,
                    json_context=json_str,
                    previous_chapters=previous_text
                )
    
    def _format_previous_chapters(self, previous_chapters: List[Chapter]) -> str:
        """Format previously completed chapters for context"""
        if not previous_chapters:
            return ""
            
        text = ""
        for chapter in previous_chapters:
            text += f"Chapter: {chapter.path_string}\n"
            # text += f"Title: {chapter.display_title}\n"
            text += f"{chapter.content}\n\n"
        return text


# --------------------------------
# Document Assembly
# --------------------------------

class LatexDocumentAssembler:
    """Assembles the final LaTeX document from generated chapters"""
    
    def create_document(self, chapters: List[Chapter], metadata: Dict[str, Any]) -> str:
        """Create a complete LaTeX document"""
        # Reorder chapters (move Notation chapter after Explanation of Assumptions)
        ordered_chapters = self._reorder_chapters(chapters)
        
        # Build document parts
        document_parts = [
            self._create_preamble(metadata),
            self._create_abstract(metadata),
            "\\maketitle",
            "\\renewcommand\\cfttoctitlefont{\\hfil\\Large\\bfseries}",
            "\\tableofcontents",
            "\\newpage",
            self._create_body(ordered_chapters, metadata),
            "\\end{document}"
        ]
        
        return "\n\n".join(document_parts)
    
    def _reorder_chapters(self, chapters: List[Chapter]) -> List[Chapter]:
        """Reorder chapters for better document structure"""
        reordered = []
        notation_chapter = next((ch for ch in chapters if ch.path == ["Notation and Explanations"]), None)
        
        for chapter in chapters:
            if chapter.path != ["Notation and Explanations"]:
                reordered.append(chapter)
                # Insert notation chapter after Explanation of Assumptions
                if notation_chapter and chapter.path == ["Explanation of Assumptions"]:
                    reordered.append(notation_chapter)
                    
        return reordered
    
    def _add_figure(self, figures: List[str]) -> str:
        """Add a figure to the content"""
        figure_str = []
        for i, figure_path in enumerate(figures):
            name = figure_path.split('/')[-1].split('.')[0].replace('_', '\\_')
            figure_str.append(f"""
\\begin{{figure}}[H]
\\centering
\\includegraphics[width=0.5\\textwidth]{{{figure_path}}}
\\caption{{{name}}}
\\end{{figure}}
""")
        return figure_str


    def _add_code(self, codes: List[str]) -> str:
        """
\subsection*{Python Code}
\subsubsection*{main1.py}

\begin{lstlisting}[language=Python, frame=single, basicstyle=\ttfamily\small]
def main1():
    pass
\end{lstlisting}
        """
        code_str = [
            "\\clearpage",
            "\\section{Appendix}",
        ]
        for i, code_path in enumerate(codes):
            with open(code_path, 'r') as f:
                code = f.read()
            name = code_path.split('/')[-1].replace('_', '\\_')
            code_str.append(f"""
\\subsubsection*{{{name}}}

\\begin{{lstlisting}}[language=Python, frame=single, basicstyle=\\ttfamily\\small]
{code}
\\end{{lstlisting}}
""")
        return code_str

    def _create_preamble(self, metadata: Dict[str, Any]) -> str:
        """Create LaTeX preamble with document setup"""
        title = metadata.get("title", "paper_title")
        team = metadata.get("team", "team")
        year = metadata.get("year", "2024")
        problem_type = metadata.get("problem_type", "problem_type")
        
        return f"""\\documentclass{{mcmthesis}}
\\mcmsetup{{CTeX = false,
        tcn = {team}, problem = {problem_type},
        year = {year},
        sheet = true, titleinsheet = true, keywordsinsheet = true,
        titlepage = false, abstract = true}}

\\usepackage{{palatino}}
\\usepackage{{algorithm}}
\\usepackage{{algpseudocode}}
\\usepackage{{tocloft}}
\\usepackage{{amsmath}}

\\usepackage{{lastpage}}
\\renewcommand{{\\cftdot}}{{.}}
\\renewcommand{{\\cftsecleader}}{{\\cftdotfill{{\\cftdotsep}}}}
\\renewcommand{{\\cftsubsecleader}}{{\\cftdotfill{{\\cftdotsep}}}}
\\renewcommand{{\\cftsubsubsecleader}}{{\\cftdotfill{{\\cftdotsep}}}}
\\renewcommand{{\\headset}}{{{year}\\\\MCM/ICM\\\\Summary Sheet}}
\\title{{{title}}}

\\begin{{document}}"""
    
    def _create_abstract(self, metadata: Dict[str, str]) -> str:
        """Create the abstract section"""
        return f"""\\begin{{abstract}}
{metadata.get('summary', '')}

\\begin{{keywords}}
{metadata.get('keywords', '')}
\\end{{keywords}}
\\end{{abstract}}"""
    
    def _create_body(self, chapters: List[Chapter], metadata: Dict[str, Any]) -> str:
        """Create the main body of the document from chapters"""
        body_parts = []
        current_path = []
        
        for chapter in chapters:
            # Add section headings
            if chapter.path == ["Model Conclusion", "Model Advantages"] and metadata.get('figures', []):
                body_parts += self._add_figure(metadata['figures'])

            for i, section in enumerate(chapter.path):
                # If this path level is new or different
                if i >= len(current_path) or section != current_path[i]:
                    # Update current path
                    if len(current_path) <= i:
                        current_path.append(section)
                    else:
                        current_path[i] = section
                        current_path = current_path[:i+1]  # Truncate the path
                
                    # Use custom title if available for the last level
                    title = chapter.display_title if i == chapter.depth - 1 else section
                    
                    # Add section heading at appropriate level
                    if i == 0:
                        body_parts.append(f"\\section{{{title}}}")
                    elif i == 1:
                        body_parts.append(f"\\subsection{{{title}}}")
                    elif i == 2:
                        body_parts.append(f"\\subsubsection{{{title}}}")
            
            # Add chapter content if generated
            if chapter.is_generated and chapter.content:
                body_parts.append(chapter.content)

        body_parts.append("\\section{References}")
        body_parts += self._add_code(metadata['codes'])
        return "\n\n".join(body_parts)

# --------------------------------
# File Operations
# --------------------------------

class FileManager:
    """Handles file operations for saving papers and generating PDFs"""
    
    @staticmethod
    def save_to_file(content: str, filepath: str) -> None:
        """Save content to a file"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Document saved to {filepath}")
    
    @staticmethod
    def generate_pdf(latex_path: str) -> None:
        """Generate a PDF from a LaTeX file"""
        print(f"Generating PDF from {latex_path}...")
        
        # Run pdflatex twice to ensure references and TOC are correct
        latex_dir = os.path.dirname(latex_path)
        subprocess.run(["pdflatex", f"-output-directory={latex_dir}", "-interaction=nonstopmode", latex_path])
        subprocess.run(["pdflatex", f"-output-directory={latex_dir}", "-interaction=nonstopmode", latex_path])
        
        # Clean up auxiliary files
        FileManager._clean_temp_files(latex_path)
        
        pdf_path = latex_path.replace('.tex', '.pdf')
        print(f"PDF generated at {pdf_path}")
    
    @staticmethod
    def _clean_temp_files(latex_path: str) -> None:
        """Clean up temporary files created during PDF generation"""
        for ext in ["aux", "log", "toc", "out"]:
            aux_file = latex_path.replace('.tex', f'.{ext}')
            if os.path.exists(aux_file):
                os.remove(aux_file)

# --------------------------------
# Main Paper Generator
# --------------------------------

class PaperGenerator:
    """Main class that orchestrates the paper generation process"""
    
    def __init__(self, llm):
        self.content_generator = ContentGenerator(llm)
        self.outline_generator = OutlineGenerator()
        self.context_extractor = ContextExtractor()
        self.prompt_creator = PromptCreator()
        self.document_assembler = LatexDocumentAssembler()
        self.file_manager = FileManager()
        self.llm = llm
        
    def generate_paper(self, 
                    json_data: Dict[str, Any], 
                    metadata: Dict[str, Any],
                    output_dir: str,
                    filename: str) -> None:
        """Generate a complete academic paper from JSON data"""
        # 1. Create chapter structure
        task_count = len(json_data.get("tasks", []))
        print(f"Starting paper generation with {task_count} tasks")
        chapters = self.outline_generator.create_outline(task_count)
        
        # Generate chapter relevance map if not provided
        chapter_relevance_map = self.outline_generator.generate_chapter_relevance_map(task_count)
        
        # 2. Generate content for each chapter that needs it
        completed_chapters = []
        for chapter in chapters:
            if chapter.needs_content:
                self._generate_chapter_content(chapter, json_data, completed_chapters, chapter_relevance_map)
                completed_chapters.append(chapter)
        
        # 3. Complete metadata if needed
        complete_metadata = self._complete_metadata(chapters, metadata)
        
        # 4. Assemble the final document
        document = self.document_assembler.create_document(chapters, complete_metadata)
        
        # 5. Save and convert to PDF
        latex_path = f"{output_dir}/{filename}.tex"
        self.file_manager.save_to_file(document, latex_path)
        self.file_manager.generate_pdf(latex_path)
        
    def _generate_chapter_content(self, 
                            chapter: Chapter, 
                            json_data: Dict[str, Any],
                            completed_chapters: List[Chapter],
                            chapter_relevance_map: Dict[str, List[str]]) -> None:
        """Generate content for a single chapter"""
        print(f"Generating content for: {chapter.path_string}")
        
        # Get relevant context data for this chapter
        context = self.context_extractor.get_context_for_chapter(chapter, json_data)
        
        # Get only the relevant completed chapters for context
        relevant_chapters = self._get_relevant_chapters(chapter, completed_chapters, chapter_relevance_map)
        
        # Create prompt and generate content
        prompt = self.prompt_creator.create_prompt(
            chapter, context, relevant_chapters
        )
        # Generate content
        response = self.content_generator.generate_chapter_content(prompt)
        
        # Update chapter with generated content
        # chapter.content = response['content']
        # chapter.title = self._format_title(chapter, response['title'])
        chapter.content = response
        chapter.title = ''
        chapter.is_generated = True
    
    def _get_relevant_chapters(self, 
                         chapter: Chapter, 
                         completed_chapters: List[Chapter],
                         chapter_relevance_map: Dict[str, List[str]]) -> List[Chapter]:
        """Filter completed chapters to only include those relevant to the current chapter"""
        # Get the path string for the current chapter
        current_path = chapter.path_string
        
        # If this chapter has specific relevant chapters defined in the map
        if current_path in chapter_relevance_map:
            relevant_paths = chapter_relevance_map[current_path]
            # Filter completed chapters to only include those in the relevant paths
            return [ch for ch in completed_chapters 
                    if ch.path_string in relevant_paths]
        
        # Default: return all completed chapters if no specific relevance is defined
        return completed_chapters

    def _format_title(self, chapter: Chapter, generated_title: str) -> str:
        """Format title based on chapter type"""
        # Only use custom titles for certain chapter types
        if (chapter.path[0] == "Problem Analysis" or 
            chapter.path[0] == "Solution to the Problem"):
            return generated_title
        return ''
    
    def _complete_metadata(self, 
                        chapters: List[Chapter], 
                        provided_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Complete paper metadata, generating missing fields if needed"""
        # If we need to generate metadata
        if not all(key in provided_metadata for key in 
                ["title", "summary", "keywords"]):
            print("Generating missing paper metadata...")
            
            # Prepare prompt with chapter contents
            chapters_text = "\n\n".join(
                f"Chapter: {ch.path_string}\n{ch.content}" 
                for ch in chapters if ch.is_generated
            )
            
            prompt = PAPER_INFO_PROMPT.format(paper_chapters=chapters_text)
            
            # Retry up to 3 times to get valid metadata
            max_retries = 3
            generated_metadata = {}
            
            for attempt in range(max_retries):
                try:
                    metadata_response = self.llm.generate(prompt)
                    generated_metadata = parse_llm_output_to_json(metadata_response)
                    if not generated_metadata:
                        raise Exception("No metadata generated")
                    break
                except Exception as e:
                    print(f"Attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_retries - 1:  # If this was the last attempt
                        print("All attempts to generate metadata failed")
            # Merge with provided metadata (provided takes precedence)
            return {**generated_metadata, **provided_metadata}
        
        return provided_metadata

# --------------------------------
# Main Function
# --------------------------------

def generate_paper_from_json(llm, json_data: dict, info: dict, output_dir: str, output_name: str) -> None:
    """Generate a paper from JSON data"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    generator = PaperGenerator(llm)
    generator.generate_paper(json_data, info, output_dir, output_name)


def generate_paper(llm, output_dir, name):
    metadata = {
        "team": "Agent",
        "year": name.split('_')[0],
        "problem_type": name.split('_')[1]
    }
    json_file_path = f"{output_dir}/json/{name}.json"
    code_dir = f'{output_dir}/code'
    metadata['figures'] = [os.path.join(code_dir, f) for f in os.listdir(code_dir) if f.lower().split('.')[-1] in ['png', 'jpg', 'jpeg']]
    metadata['codes'] = sorted([os.path.join(code_dir, f) for f in os.listdir(code_dir) if f.lower().split('.')[-1] in ['py']])
    with open(json_file_path, 'r') as f:
        json_data = json.loads(f.read())
    json_data['tasks'] = json_data['tasks'][:]

    # Generate paper with chapter relevance mapping
    generate_paper_from_json(llm, json_data, metadata, f"{output_dir}/latex", 'solution')

