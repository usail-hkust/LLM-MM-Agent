from .base_agent import BaseAgent
from prompt.template import (TASK_ANALYSIS_PROMPT, TASK_RESULT_PROMPT, TASK_ANSWER_PROMPT, 
                             TASK_FORMULAS_PROMPT, TASK_FORMULAS_CRITIQUE_PROMPT, TASK_FORMULAS_IMPROVEMENT_PROMPT, 
                             TASK_MODELING_PROMPT, TASK_MODELING_CRITIQUE_PROMPT, TASK_MODELING_IMPROVEMENT_PROMPT,
                             TASK_CODING_PROMPT, TASK_CODING_DEBUG_PROMPT, CODE_STRUCTURE_PROMPT, 
                             TASK_RESULT_WITH_CODE_PROMPT)
import sys
import os
import subprocess
import selectors
import tiktoken
import json


class EnvException(Exception):
    def __init__(self, message):
        self.message = message 
    def __str__(self):
        return self.message
    

def execute_script(script_path, work_dir):
    try:
        device = 0
        python = "python"
        cmd = f"CUDA_VISIBLE_DEVICES={device} {python} -u {script_path}"
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, cwd=work_dir)

        stdout_lines = []
        stderr_lines = []

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)

        while process.poll() is None and selector.get_map():
            events = selector.select(timeout=1)

            for key, _ in events:
                line = key.fileobj.readline()
                if key.fileobj == process.stdout:
                    print("STDOUT:", line, end =" ")
                    stdout_lines.append(line)
                else:
                    print("STDERR:", line, end =" ")
                    stderr_lines.append(line)

        for line in process.stdout:
            line = line
            print("STDOUT:", line, end =" ")
            stdout_lines.append(line)
        for line in process.stderr:
            line = line
            print("STDERR:", line, end =" ")
            stderr_lines.append(line)

        return_code = process.returncode

        if return_code != 0:
            observation = "".join(stderr_lines)
        else:
            observation = "".join(stdout_lines)
        if observation == "" and return_code == 0:
            # printed to stderr only
            observation = "".join(stderr_lines)
        return "The script has been executed. Here is the output:\n" + observation
    except Exception as e:
        print("++++", "Wrong!")
        raise EnvException(f"Something went wrong in executing {script_path}: {e}. Please check if it is ready to be executed.")


class TaskSolver(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)

    def analysis(self, prompt: str, task_description: str, user_prompt: str = ''):
        prompt = TASK_ANALYSIS_PROMPT.format(prompt=prompt, task_description=task_description, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)
    
    def formulas_actor(self, prompt: str, data_summary: str, task_description: str, task_analysis: str, modeling_methods: str, user_prompt: str = ''):
        prompt = TASK_FORMULAS_PROMPT.format(prompt=prompt, data_summary=data_summary, task_description=task_description, task_analysis=task_analysis, modeling_methods=modeling_methods, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def formulas_critic(self, data_summary: str, task_description: str, task_analysis: str, modeling_formulas: str):
        prompt = TASK_FORMULAS_CRITIQUE_PROMPT.format(data_summary=data_summary, task_description=task_description, task_analysis=task_analysis, modeling_formulas=modeling_formulas).strip()
        return self.llm.generate(prompt)
    
    def formulas_improvement(self, data_summary: str, task_description: str, task_analysis: str, modeling_formulas: str, modeling_formulas_critique: str, user_prompt: str = ''):
        prompt = TASK_FORMULAS_IMPROVEMENT_PROMPT.format(data_summary=data_summary, task_description=task_description, task_analysis=task_analysis, modeling_formulas=modeling_formulas, modeling_formulas_critique=modeling_formulas_critique, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def modeling(self, formulas_prompt: str, modeling_prompt: str, data_summary: str, task_description: str, task_analysis: str, modeling_methods: str, round: int = 1, user_prompt: str = ''):
        formulas = self.formulas_actor(formulas_prompt, data_summary, task_description, task_analysis, modeling_methods, user_prompt)
        for i in range(round):
            formulas_critique = self.formulas_critic(data_summary, task_description, task_analysis, formulas)
            formulas = self.formulas_improvement(data_summary, task_description, task_analysis, formulas, formulas_critique, user_prompt)
        
        modeling_method = self.modeling_actor(modeling_prompt, data_summary, task_description, task_analysis, formulas, user_prompt)
    
        return formulas, modeling_method

    def modeling_actor(self, prompt: str, data_summary: str, task_description: str, task_analysis: str, formulas: str, user_prompt: str = ''):
        prompt = TASK_MODELING_PROMPT.format(prompt=prompt, data_summary=data_summary, task_description=task_description, task_analysis=task_analysis, modeling_formulas=formulas, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    # def modeling_critic(self, task_description: str, task_analysis: str, data_summary: str, formulas: str, modeling_process: str):
    #     prompt = TASK_MODELING_CRITIQUE_PROMPT.format(task_description=task_description, task_analysis=task_analysis, data_summary=data_summary, modeling_formulas=formulas, modeling_process=modeling_process).strip()
    #     return self.llm.generate(prompt)
    
    # def modeling_improvement(self, task_description: str, task_analysis: str, data_summary: str, formulas: str, modeling_process: str, modeling_process_critique: str):
    #     prompt = TASK_MODELING_IMPROVEMENT_PROMPT.format(task_description=task_description, task_analysis=task_analysis, data_summary=data_summary, modeling_formulas=formulas, modeling_process=modeling_process, modeling_process_critique=modeling_process_critique).strip()
    #     return self.llm.generate(prompt)

    # def modeling(self, task_description: str, task_analysis: str, data_summary: str, formulas: str, round: int = 1):
    #     process = self.modeling_actor(task_description, task_analysis, data_summary, formulas)
    #     for i in range(round):
    #         print(f'MODELING Round {i+1}')
    #         process_critique = self.modeling_critic(task_description, task_analysis, data_summary, formulas, process)
    #         process = self.modeling_improvement(task_description, task_analysis, data_summary, formulas, process, process_critique)
    #     return process
    
    def coding_actor(self, data_file, data_summary, variable_description, task_description: str, task_analysis: str, formulas: str, modeling: str, dependent_file_prompt: str, code_template: str, script_name: str, work_dir: str, user_prompt: str = ''):
        prompt = TASK_CODING_PROMPT.format(data_file=data_file, data_summary=data_summary, variable_description=variable_description, task_description=task_description, task_analysis=task_analysis, modeling_formulas=formulas, modeling_process=modeling, dependent_file_prompt=dependent_file_prompt, code_template=code_template, user_prompt=user_prompt).strip()
        max_retry = 0
        while max_retry < 5:
            max_retry += 1
            try:
                completion = self.llm.generate(prompt)
                new_content = completion.split("```python")[1].split("```")[0].strip()
                break  
            except Exception as e:
                # Format control.
                print(f"Retry! The code does not start with ```python")
                continue

        with open(os.path.join(work_dir, script_name), "w") as f:
            f.write(new_content)
        
        # Execute the script.
        try:
            observation = execute_script(script_name, work_dir)
            ## If observation is too long, we only keep the last ~2k tokens.
            enc = tiktoken.get_encoding("cl100k_base")
            tokens = len(enc.encode(observation))
            if tokens >= 2000:
                observation = observation[:2000]
                tokens = len(enc.encode(observation))
        except Exception as e:
            print(e)
            input("Ah oh, Got stuck! Press any key to continue.")

        return new_content, observation
    
    def coding_debugger(self, code_template: str, modeling: str, code: str, observation: str, script_name: str, work_dir: str, user_prompt: str = ''):
        
        prompt = TASK_CODING_DEBUG_PROMPT.format(code_template=code_template, modeling_process=modeling, code=code, observation=observation, user_prompt=user_prompt).strip()
        
        max_retry = 0
        while max_retry < 5:
            max_retry += 1
            try:
                completion = self.llm.generate(prompt)
                new_content = completion.split("```python")[1].split("```")[0].strip()
                break  
            except Exception as e:
                # Format control.
                print(f"Retry! The code does not start with ```python")
                continue

        with open(os.path.join(work_dir, script_name), "w") as f:
            f.write(new_content)
        
        # Execute the script.
        try:
            observation = execute_script(script_name, work_dir)
            ## If observation is too long, we only keep the last ~2k tokens.
            enc = tiktoken.get_encoding("cl100k_base")
            tokens = len(enc.encode(observation))
            if tokens >= 2000:
                observation = observation[:2000]
                tokens = len(enc.encode(observation))
        except Exception as e:
            print(e)
            input("Ah oh, Got stuck! Press any key to continue.")

        return new_content, observation
    
    def coding(self, data_file, data_summary, variable_description, task_description: str, task_analysis: str, formulas: str, modeling: str, dependent_file_prompt: str, code_template: str, script_name: str, work_dir: str, try_num: int = 5, round: int = 1, user_prompt: str = ''):
        for i in range(try_num):
            print("="*10 + f" Try: {i + 1} " + "="*10)
            iteration = 0
            max_iteration = 3
            while iteration < max_iteration:
                print("="*10 + f" Iteration: {iteration + 1} " + "="*10)
                if iteration == 0:
                    code, observation = self.coding_actor(data_file, data_summary, variable_description, task_description, task_analysis, formulas, modeling, dependent_file_prompt, code_template, script_name, work_dir, user_prompt)
                    # If the script has been successfully executed: Exit.
                    if "Traceback (most recent call last):" not in observation and "SyntaxError: invalid syntax" not in observation and "IndentationError" not in observation:
                        return code, True, observation.split("The script has been executed. Here is the output:\n")[1]
                else:
                    code, observation = self.coding_debugger(code_template, modeling, code, observation, script_name, work_dir, user_prompt)
                    # If the script has been successfully executed: Exit.
                    if "Traceback (most recent call last):" not in observation and "SyntaxError: invalid syntax" not in observation and "IndentationError" not in observation:
                        return code, True, observation.split("The script has been executed. Here is the output:\n")[1]
                iteration += 1

        return code, False, None

    def result(self, task_description: str, task_analysis: str, task_formulas: str, task_modeling: str, user_prompt: str = '', execution_result: str = ''):
        if execution_result == '':
            prompt = TASK_RESULT_PROMPT.format(task_description=task_description, task_analysis=task_analysis, task_formulas=task_formulas, task_modeling=task_modeling, user_prompt=user_prompt).strip()
        else:
            prompt = TASK_RESULT_WITH_CODE_PROMPT.format(task_description=task_description, task_analysis=task_analysis, task_formulas=task_formulas, task_modeling=task_modeling, user_prompt=user_prompt, execution_result=execution_result).strip()
        return self.llm.generate(prompt)

    def answer(self, task_description: str, task_analysis: str, task_formulas: str, task_modeling: str, task_result: str, user_prompt: str = ''):
        prompt = TASK_ANSWER_PROMPT.format(task_description=task_description, task_analysis=task_analysis, task_formulas=task_formulas, task_modeling=task_modeling, task_result=task_result, user_prompt=user_prompt).strip()
        return self.llm.generate(prompt)

    def extract_code_structure(self, task_id, code: str, save_path: str):
        prompt = CODE_STRUCTURE_PROMPT.format(code=code, save_path=save_path)
        count = 0
        for i in range(5):
            try:
                strucutre = self.llm.generate(prompt)
                structure_string = strucutre.strip('```json\n').strip('```')
                structure_json = json.loads(structure_string)
                for i in range(len(structure_json['file_outputs'])):
                    structure_json['file_outputs'][i]['file_description'] = 'This file is generated by code for Task {}. '.format(task_id) + structure_json['file_outputs'][i]['file_description']
                return structure_json
            except:
                continue
        if count == 5:
            sys.exit("Fail at extract_code_structure")
