import os
import requests
import openai
from dotenv import load_dotenv
import json

load_dotenv()

class LLM:

    usages = []
    def __init__(self, model_name, key, logger=None, user_id=None):
        self.model_name = model_name
        self.logger = logger
        self.user_id = user_id
        self.api_key = key
        if self.model_name in ['deepseek-chat', 'deepseek-reasoner']:
            self.api_base = os.getenv('DEEPSEEK_API_BASE')
        elif self.model_name in ['qwen2.5-72b-instruct']:
            self.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif self.model_name in ['gpt-4o', 'gpt-4']:
            self.api_base = os.getenv('OPENAI_API_BASE')
        
        if not self.api_key:
            raise ValueError('API key not found in environment variables')

        self.client = openai.Client(api_key=self.api_key, base_url=self.api_base)

    def reset(self, api_key=None, api_base=None, model_name=None):
        if api_key:
            self.api_key = api_key
        if api_base:
            self.api_base = api_base
        if model_name:
            self.model_name = model_name
        self.client = openai.Client(api_key=self.api_key, base_url=self.api_base)

    def generate(self, prompt, system='', usage=True):
        try:
            if self.model_name in ['deepseek-chat', 'deepseek-reasoner']:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.7,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                answer = response.choices[0].message.content
                usage = {
                    'completion_tokens': response.usage.completion_tokens,
                    'prompt_tokens': response.usage.prompt_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            elif self.model_name in ['gpt-4o', 'gpt-4']:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.7,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                answer = response.choices[0].message.content
                usage = {
                    'completion_tokens': response.usage.completion_tokens,
                    'prompt_tokens': response.usage.prompt_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            elif self.model_name in ['qwen2.5-72b-instruct']:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.7,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                answer = response.choices[0].message.content
                usage = {
                    'completion_tokens': response.usage.completion_tokens,
                    'prompt_tokens': response.usage.prompt_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            if self.logger:
                self.logger.info(f"[LLM] UserID: {self.user_id} Key: {self.api_key}, Model: {self.model_name}, Usage: {usage}")
            if usage:
                self.usages.append(usage)
            return answer

        except Exception as e:
            return f'An error occurred: {e}'

    def get_total_usage(self):
        total_usage = { 
            'completion_tokens': 0,
            'prompt_tokens': 0,
            'total_tokens': 0
        }
        for usage in self.usages:
            for key, value in usage.items():
                total_usage[key] += value
        return total_usage
        
    def clear_usage(self):
        self.usages = []