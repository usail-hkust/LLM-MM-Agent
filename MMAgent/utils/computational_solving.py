import os
from utils.utils import save_solution
from agent.task_solving import TaskSolver
from agent.create_charts import ChartCreator


def computational_solving(llm, coordinator, with_code, problem, task_id, task_description, task_analysis, task_modeling_formulas, task_modeling_method, dependent_file_prompt, config, solution, name, output_dir):
    ts = TaskSolver(llm)
    cc = ChartCreator(llm)
    code_template = open(os.path.join('MMAgent/code_template','main{}.py'.format(task_id))).read()
    save_path = os.path.join(output_dir,'code/main{}.py'.format(task_id))
    work_dir = os.path.join(output_dir,'code')
    script_name = 'main{}.py'.format(task_id)

    if with_code:
        task_code, is_pass, execution_result = ts.coding(problem['dataset_path'], problem['data_description'], problem['variable_description'], task_description, task_analysis, task_modeling_formulas, task_modeling_method, dependent_file_prompt, code_template, script_name, work_dir)
        code_structure = ts.extract_code_structure(task_id, task_code, save_path)
        task_result = ts.result(task_description, task_analysis, task_modeling_formulas, task_modeling_method, execution_result)
        task_answer = ts.answer(task_description, task_analysis, task_modeling_formulas, task_modeling_method, task_result)
        task_dict = {
            'task_description': task_description,
            'task_analysis': task_analysis,
            'preliminary_formulas': task_modeling_formulas,
            'mathematical_modeling_process': task_modeling_method,
            'task_code': task_code,
            'is_pass': is_pass,
            'execution_result': execution_result,
            'solution_interpretation': task_result,
            'subtask_outcome_analysis': task_answer
        }
        coordinator.code_memory[str(task_id)] = code_structure
    else:
        task_result = ts.result(task_description, task_analysis, task_modeling_formulas, task_modeling_method)
        task_answer = ts.answer(task_description, task_analysis, task_modeling_formulas, task_modeling_method, task_result)
        task_dict = {
            'task_description': task_description,
            'task_analysis': task_analysis,
            'preliminary_formulas': task_modeling_formulas,
            'mathematical_modeling_process': task_modeling_method,
            'solution_interpretation': task_result,
            'subtask_outcome_analysis': task_answer
        }
    coordinator.memory[str(task_id)] = task_dict
    charts = cc.create_charts(str(task_dict), config['chart_num'])
    task_dict['charts'] = charts
    solution['tasks'].append(task_dict)
    save_solution(solution, name, output_dir)
    return solution