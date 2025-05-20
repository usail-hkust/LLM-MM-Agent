from .base_agent import BaseAgent
from prompt.template import PROBLEM_ANALYSIS_PROMPT, PROBLEM_ANALYSIS_CRITIQUE_PROMPT, PROBLEM_ANALYSIS_IMPROVEMENT_PROMPT, PROBLEM_MODELING_PROMPT, PROBLEM_MODELING_CRITIQUE_PROMPT, PROBLEM_MODELING_IMPROVEMENT_PROMPT


class ProblemUnderstanding(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
    
    def analysis_actor(self, modeling_problem: str, user_prompt: str=''):
        prompt = PROBLEM_ANALYSIS_PROMPT.format(modeling_problem=modeling_problem, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def analysis_critic(self, modeling_problem: str, problem_analysis: str):
        prompt = PROBLEM_ANALYSIS_CRITIQUE_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis).strip()
        return self.llm.generate(prompt)

    def analysis_improvement(self, modeling_problem: str, problem_analysis: str, problem_analysis_critique: str, user_prompt: str=''):
        prompt = PROBLEM_ANALYSIS_IMPROVEMENT_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, problem_analysis_critique=problem_analysis_critique, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def analysis(self, modeling_problem: str, round: int = 3, user_prompt: str = ''):
        problem_analysis = self.analysis_actor(modeling_problem, user_prompt)
        for i in range(round):
            problem_analysis_critique = self.analysis_critic(modeling_problem, problem_analysis)
            problem_analysis_improvement = self.analysis_improvement(modeling_problem, problem_analysis, problem_analysis_critique, user_prompt)
            problem_analysis = problem_analysis_improvement
        return problem_analysis

    def modeling_actor(self, modeling_problem: str, problem_analysis: str, user_prompt: str=''):
        prompt = PROBLEM_MODELING_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def modeling_critic(self, modeling_problem: str, problem_analysis: str, modeling_solution: str):
        prompt = PROBLEM_MODELING_CRITIQUE_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution).strip()
        return self.llm.generate(prompt)

    def modeling_improvement(self, modeling_problem: str, problem_analysis: str, modeling_solution: str, modeling_solution_critique: str, user_prompt: str=''):
        prompt = PROBLEM_MODELING_IMPROVEMENT_PROMPT.format(modeling_problem=modeling_problem, problem_analysis=problem_analysis, modeling_solution=modeling_solution, modeling_solution_critique=modeling_solution_critique, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def modeling(self, modeling_problem: str, problem_analysis: str, round: int = 3, user_prompt: str = ''):
        modeling_solution = self.modeling_actor(modeling_problem, problem_analysis, user_prompt)
        for i in range(round):
            modeling_solution_critique = self.modeling_critic(modeling_problem, problem_analysis, modeling_solution)
            modeling_solution_improvement = self.modeling_improvement(modeling_problem, problem_analysis, modeling_solution, modeling_solution_critique, user_prompt)
            modeling_solution = modeling_solution_improvement
        return modeling_solution