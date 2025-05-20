import os
from utils.utils import read_json_file
from agent.data_description import DataDescription
from agent.problem_analysis import ProblemUnderstanding
from agent.coordinator import Coordinator
from agent.problem_decompse import ProblemDecompose
from prompt.template import PROBLEM_PROMPT
import shutil


def get_problem(problem_path, llm):
    problem = read_json_file(problem_path)
    data_description = problem.get('dataset_description', {})
    ds = DataDescription(llm)
    
    if data_description:
        data_path = problem['dataset_path']
        variable_description = problem['variable_description']
        data_summary = ds.summary(data_description=str(data_description) + '\n' + str(variable_description))
        data_summary = f'Dataset Path:\n{data_path}\n\nData Description:\n{data_summary}'
    else:
        data_summary = ''

    problem['data_summary'] = data_summary
    problem['data_description'] = data_description

    if problem.get('addendum', ''):
        addendum = f"Addendum: \n{problem['addendum']}"
    else:
        addendum = ''

    problem_str = PROBLEM_PROMPT.format(problem_background=problem['background'], problem_requirement=problem['problem_requirement'], addendum=addendum, data_summary=data_summary).strip()
    problem['problem_str'] = problem_str
    return problem_str, problem


def problem_analysis(llm, problem_path, config, dataset_path, output_dir):
    # Get problem
    problem_str, problem = get_problem(problem_path, llm)
    problem_type = os.path.splitext(os.path.basename(problem_path))[0].split('_')[-1]
    
    # Initialize solution dictionary
    solution = {'tasks': []}
    solution['problem_background'] = problem['background']
    solution['problem_requirement'] = problem['problem_requirement']

    # Problem Understanding
    pu = ProblemUnderstanding(llm)
    problem_analysis = pu.analysis(problem_str, round=config['problem_analysis_round'])
    solution['problem_analysis'] = problem_analysis

    # High level probelm understanding modeling
    modeling_solution = pu.modeling(problem_str, problem_analysis, round=config['problem_modeling_round'])
    print('********************* Step 1: Problem Understanding finish *********************')

    # Problem Decomposition
    pd = ProblemDecompose(llm)
    task_descriptions = pd.decompose_and_refine(problem_str, problem_analysis, modeling_solution, problem_type, config['tasknum'])
    print('********************* Step 2: Problem Decomposition finish *********************')

    # Task Dependency Analysis
    with_code = len(problem['dataset_path']) > 0
    coordinator = Coordinator(llm)
    order = coordinator.analyze_dependencies(problem_str, problem_analysis, modeling_solution, task_descriptions, with_code)
    order = [int(i) for i in order]
    if with_code:
        shutil.copytree(dataset_path, os.path.join(output_dir,'code'), dirs_exist_ok=True)
    print('********************* Step 3: Task Dependency Analysis finish *********************')

    return problem, order, with_code, coordinator, task_descriptions, solution