from collections import deque
from prompt.template import TASK_DEPENDENCY_ANALYSIS_WITH_CODE_PROMPT, TASK_DEPENDENCY_ANALYSIS_PROMPT, DAG_CONSTRUCTION_PROMPT, CODE_STRUCTURE_PROMPT
import json
import sys

class Coordinator:
    def __init__(self, llm):
        self.llm = llm
        self.memory = {}
        self.code_memory = {}

    def compute_dag_order(self, graph):
        """
        Compute the topological sorting (computation order) of a DAG.
        :param graph: DAG represented as an adjacency list, in the format of {node: [other nodes that this node depends on]}.
        :return: A list representing the computation order.
        """
        # Calculate indegree
        in_degree = {node: 0 for node in graph}
        for node in graph:
            in_degree[node] += len(graph[node])

        # Find all nodes with in-degree 0 (which can be used as the starting point for calculation)
        queue = deque([node for node in in_degree if in_degree[node] == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)

            # Traverse all nodes, find the nodes that depend on the current node, and reduce their in-degree
            for neighbor in graph:
                if node in graph[neighbor]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # Check if there is a loop (if the number of sorted nodes is less than the total number of nodes, then there is a loop)
        if len(order) != len(graph):
            raise ValueError("Graph contains a cycle!")

        return order
    
    def analyze(self, tasknum: int, modeling_problem: str, problem_analysis: str, modeling_solution: str, task_descriptions: str, with_code: bool):
        if with_code:
            prompt = TASK_DEPENDENCY_ANALYSIS_WITH_CODE_PROMPT.format(tasknum=tasknum, modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, task_descriptions=task_descriptions).strip()
        else:
            prompt = TASK_DEPENDENCY_ANALYSIS_PROMPT.format(tasknum=tasknum, modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, task_descriptions=task_descriptions).strip()
        return self.llm.generate(prompt)

    def dag_construction(self, tasknum: int, modeling_problem: str, problem_analysis: str, modeling_solution: str, task_descriptions: str, task_dependency_analysis: str):
        prompt = DAG_CONSTRUCTION_PROMPT.format(tasknum=tasknum, modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, task_descriptions=task_descriptions, task_dependency_analysis=task_dependency_analysis).strip()
        return self.llm.generate(prompt)

    def analyze_dependencies(self, modeling_problem: str, problem_analysis: str, modeling_solution: str, task_descriptions: str, with_code: bool):
        task_dependency_analysis = self.analyze(len(task_descriptions), modeling_problem, problem_analysis, modeling_solution, task_descriptions, with_code)
        self.task_dependency_analysis = task_dependency_analysis.split('\n\n')
        count = 0
        for i in range(5):
            try:
                dependency_DAG = self.dag_construction(len(task_descriptions), modeling_problem, problem_analysis, modeling_solution, task_descriptions, task_dependency_analysis)
                dependency_DAG_string = dependency_DAG.strip('```json\n').strip('```')
                self.DAG = json.loads(dependency_DAG_string)
                break
            except:
                continue
        if count == 5:
            sys.exit("Fail at Task Dependency Analysis")
        order = self.compute_dag_order(self.DAG)

        return order
    
    