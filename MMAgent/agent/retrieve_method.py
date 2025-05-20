import json
from typing import List
from functools import partial
from .base_agent import BaseAgent
from prompt.template import METHOD_CRITIQUE_PROMPT
from utils.convert_format import markdown_to_json_method
from utils.utils import parse_llm_output_to_json
from utils.embedding import EmbeddingScorer

import json


class MethodScorer:

    def __init__(self, score_func, parent_weight=0.5, child_weight=0.5):
        self.parent_weight = parent_weight
        self.child_weight = child_weight
        self.score_func = score_func
        self.leaves = []

    def process(self, data):
        self.leaves = []
        for root_node in data:
            self._process_node(root_node, parent_scores=[])
        for root_node in data:
            self._collect_leaves(root_node)
        return self.leaves

    def _process_node(self, node, parent_scores):
        if 'children' in node:
            children = node.get('children', [])
            if children:
                first_child = children[0]
                if 'method_class' in first_child:
                    input_for_llm = [{"method": child["method_class"], "description": child.get("description", "")} for child in children]
                    llm_result = self.score_func(input_for_llm)
                    for idx, child in enumerate(children):
                        if idx < len(llm_result):
                            child['score'] = llm_result[idx]['score']
                        else:
                            child['score'] = 0
                    current_score = node.get('score')
                    new_parent = parent_scores.copy()
                    if current_score is not None:
                        new_parent.append(current_score)
                    for child in children:
                        self._process_node(child, new_parent)
                else:
                    input_for_llm = [{"method": child["method"], "description": child.get("description", "")} for child in children]
                    llm_result = self.score_func(input_for_llm)
                    for idx, child in enumerate(children):
                        if idx < len(llm_result):
                            child_score = llm_result[idx]['score']
                        else:
                            child_score = 0
                        child['score'] = child_score
                        parent_avg = sum(parent_scores) / len(parent_scores) if parent_scores else 0
                        final_score = parent_avg * self.parent_weight + child_score * self.child_weight
                        child['final_score'] = final_score

    def _collect_leaves(self, node):
        if 'children' in node:
            for child in node['children']:
                self._collect_leaves(child)
        else:
            if 'final_score' in node:
                self.leaves.append({
                    "method": node["method"],
                    "description": node.get("description", ""),
                    "score": node['final_score']
                })


class MethodRetriever(BaseAgent):
    def __init__(self, llm, rag=True):
        super().__init__(llm)
        self.rag = rag
        self.embedding_scorer = EmbeddingScorer()
        json_path = 'MMAgent/HMML/HMML.json'
        md_path = 'MMAgent/HMML/HMML.md'

        with open(str(md_path), "r", encoding="utf-8") as f:
            self.markdown_text = f.read()
        self.method_tree = markdown_to_json_method(self.markdown_text)
        with open(json_path, "w+", encoding="utf-8") as f:
            json.dump(self.method_tree, f, ensure_ascii=False, indent=4)
        
    def llm_score_method(self, problem_description: str, methods: List[dict]):
        methods_str = '\n'.join([f"{i+1}. {method['method']} {method.get('description', '')}" for i, method in enumerate(methods)])
        prompt = METHOD_CRITIQUE_PROMPT.format(problem_description=problem_description, methods=methods_str)
        answer = self.llm.generate(prompt)
        method_scores = parse_llm_output_to_json(answer).get('methods', [])
        method_scores = sorted(method_scores, key=lambda x: x['method_index'])
        for method in method_scores:
            method['score'] = sum(method['scores'].values()) / len(method['scores'])
        return method_scores

    def format_methods(self, methods: List[str]):
        return '\n'.join([f"**{method['method']}:** {method['description']}" for method in methods])

    def retrieve_meethods(self, problem_description: str, top_k: int=6, method: str='embedding'):
        if self.rag:
            if method == 'embedding':
                score_func = partial(self.embedding_scorer.score_method, problem_description)
            else:
                score_func = partial(self.llm_score_method, problem_description)
            method_scores = MethodScorer(score_func).process(self.method_tree)
            method_scores.sort(key=lambda x: x['score'], reverse=True)
            return self.format_methods(method_scores[:top_k])
        else:
            return self.markdown_text