from llm.llm import LLM
from utils.utils import write_json_file, get_info
import time
import argparse
from utils.problem_analysis import problem_analysis
from utils.mathematical_modeling import mathematical_modeling
from utils.computational_solving import computational_solving
from utils.solution_reporting import generate_paper


def run(key, problem_path, config, name, dataset_path, output_dir):
    # Initialize LLM
    llm = LLM(config['model_name'], key)

    # Stage 1: Problem Analysis
    print('********************* Stage 1: Problem Analysis start *********************')
    problem, order, with_code, coordinator, task_descriptions, solution = problem_analysis(llm, problem_path, config, dataset_path, output_dir)
    print('********************* Stage 1: Problem Analysis finish *********************')

    # Stage 2 & 3: Mathematical Modeling & Computational Solving
    print('********************* Stage 2 & 3: Mathematical Modeling & Computational Solving start *********************')
    for id in order:
        print('********************* Solving Task {} *********************'.format(id))
        task_description, task_analysis, task_modeling_formulas, task_modeling_method, dependent_file_prompt = mathematical_modeling(id, problem, task_descriptions, llm, config, coordinator, with_code)
        solution = computational_solving(llm, coordinator, with_code, problem, id, task_description, task_analysis, task_modeling_formulas, task_modeling_method, dependent_file_prompt, config, solution, name, output_dir)
    print('********************* Stage 2 & 3: Mathematical Modeling & Computational Solving finish *********************')    
    
    # # optional
    # print('********************* Stage 4: Solution Reporting start *********************')
    # paper = generate_paper(llm, output_dir, name)
    # print('********************* Stage 4: Solution Reporting finish *********************')

    print(solution)
    print('Usage:', llm.get_total_usage())
    write_json_file(f'{output_dir}/usage/{name}.json', llm.get_total_usage())


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_name', type=str, default='gpt-4o')
    parser.add_argument('--method_name', type=str, default='MM-Agent')
    parser.add_argument('--task', type=str, default='2024_C')
    parser.add_argument('--key', type=str, default='')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    problem_path, config, dataset_dir, output_dir = get_info(args)
    start = time.time()
    solution = run(key=args.key, problem_path=problem_path, config=config, name=args.task, dataset_path=dataset_dir, output_dir=output_dir)
    end = time.time()
    with open(output_dir + '/usage/runtime.txt', 'w') as f:
        f.write("{:.2f}s".format(end - start))
