from .base_agent import BaseAgent
from prompt.template import DATA_DESCRIPTION_PROMPT

class DataDescription(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
    
    def summary(self, data_description: str):
        prompt = DATA_DESCRIPTION_PROMPT.format(data_description=data_description)
        return self.llm.generate(prompt)

