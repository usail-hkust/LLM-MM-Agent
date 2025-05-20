from typing import List
from .base_agent import BaseAgent
from prompt.template import TASK_DECOMPOSE_PROMPT, TASK_DESCRIPTION_PROMPT
from utils.utils import read_json_file


class ProblemDecompose(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
        self.decomposed_principles = read_json_file('MMAgent/prompt/decompose_prompt.json')

    def decompose(self, modeling_problem: str, problem_analysis: str, modeling_solution: str, problem_type: str, tasknum: int, user_prompt: str=''):
        decomposed_principle = self.decomposed_principles.get(problem_type, self.decomposed_principles['C'])
        decomposed_principle = decomposed_principle.get(str(tasknum), decomposed_principle['4'])
        prompt = TASK_DECOMPOSE_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, decomposed_principle=decomposed_principle, tasknum=tasknum, user_prompt=user_prompt)
        answer = self.llm.generate(prompt)
        tasks = [task.strip() for task in answer.split('---') if task.strip()]
        return tasks

    def refine(self, modeling_problem: str, problem_analysis: str, modeling_solution: str, decomposed_subtasks: List[str], task_i: int):
        decomposed_subtasks_str = '\n'.join(decomposed_subtasks)
        prompt = TASK_DESCRIPTION_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, decomposed_subtasks=decomposed_subtasks_str, task_i=task_i+1)
        answer = self.llm.generate(prompt)
        return answer

    def decompose_and_refine(self, modeling_problem: str, problem_analysis: str, modeling_solution: str, decomposed_principle: str, tasknum: int, user_prompt: str=''):
        decomposed_subtasks = self.decompose(modeling_problem, problem_analysis, modeling_solution, decomposed_principle, tasknum, user_prompt)
        for task_i in range(len(decomposed_subtasks)):
            refined_subtask = self.refine(modeling_problem, problem_analysis, modeling_solution, decomposed_subtasks, task_i)
            decomposed_subtasks[task_i] = refined_subtask
        return decomposed_subtasks
