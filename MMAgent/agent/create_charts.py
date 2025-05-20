from .base_agent import BaseAgent
from prompt.template import CREATE_CHART_PROMPT

class ChartCreator(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
    
    def create_single_chart(self, paper_content: str, existing_charts: str, user_prompt: str=''):
        prompt = CREATE_CHART_PROMPT.format(paper_content=paper_content, existing_charts=existing_charts, user_prompt=user_prompt)
        return self.llm.generate(prompt)

    def create_charts(self, paper_content: str, chart_num: int, user_prompt: str=''):
        existing_charts = ''
        charts = []
        for i in range(chart_num):
            chart = self.create_single_chart(paper_content, existing_charts, user_prompt)
            charts.append(chart)
            existing_charts = '\n---\n'.join(charts)
        return charts
