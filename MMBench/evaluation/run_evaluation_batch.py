import os
import json
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluation.model import gpt
from functools import partial
from evaluation.utils import load_json, load_solution_json
from evaluation.prompts import generate_problem_analysis_prompt, generate_modeling_rigorousness_prompt, generate_practicality_and_scientificity_prompt, generate_result_and_bias_analysis_prompt
import argparse


def parse_and_save_evaluation_data(text):
    """
    Parse evaluation text and save as a dictionary, and return it
    """
    reason_pattern = r'<reason>\s*(.*?)\s*</reason>'
    score_pattern = r'<score>\s*(\d+)\s*</score>'

    reasons = re.findall(reason_pattern, text, re.DOTALL)
    scores = re.findall(score_pattern, text, re.DOTALL)

    if not reasons or not scores:
        print("No matches found for reasons or scores!")
        return {}

    if len(reasons) != len(scores):
        print("Mismatch between number of reasons and scores!")
        return {}

    result_dict = {}
    for i, (reason, score) in enumerate(zip(reasons, scores), 1):
        result_dict[f"analysis_{i}"] = {
            "reason": reason.strip(),
            "score": int(score)
        }

    return result_dict


def evaluate_math_modeling(llm, solution_path):
    print("=== Starting math modeling evaluation ===")
    
    # get file name
    file_name = os.path.basename(solution_path).split('.')[0]

    # define evaluation result directory
    base_dir = os.path.dirname(solution_path)
    evaluation_dir = os.path.join(base_dir, "evaluation_result")
    if not os.path.exists(evaluation_dir):
        os.makedirs(evaluation_dir)
    if not os.path.exists(os.path.join(evaluation_dir, file_name)):
        os.makedirs(os.path.join(evaluation_dir, file_name))
    evaluation_dir = os.path.join(evaluation_dir, file_name)
    print(f"Evaluation directory created at: {evaluation_dir}")

    # define evaluation result path
    evaluation_results_txt_path = os.path.join(evaluation_dir, 'evaluation_results.txt')
    evaluation_results_json_path = os.path.join(evaluation_dir, 'evaluation_results.json')
    
    # Load JSON file
    print("=== Loading solution.json file ===")
    solution_data = load_solution_json(solution_path)

    if not solution_data:
        print("Error: Unable to load solution.json file.")
        return

    # Generate evaluation prompts
    print("=== Generating evaluation prompts ===")
    problem_analysis_evaluation_prompt = generate_problem_analysis_prompt(solution_data)
    analysis_evaluation_results = llm(problem_analysis_evaluation_prompt)
    print("=== Completed problem analysis evaluation ===")

    modeling_rigorousness_evaluation_prompt = generate_modeling_rigorousness_prompt(solution_data)
    modeling_rigorousness_evaluation_results = llm(modeling_rigorousness_evaluation_prompt)
    print("=== Completed modeling rigorousness evaluation ===")

    practicality_and_scientificity_evaluation_prompt = generate_practicality_and_scientificity_prompt(solution_data)
    practicality_and_scientificity_evaluation_results = llm(practicality_and_scientificity_evaluation_prompt)
    print("=== Completed practicality and scientificity evaluation ===")

    result_and_bias_analysis_evaluation_prompt = generate_result_and_bias_analysis_prompt(solution_data)
    result_and_bias_analysis_evaluation_results = llm(result_and_bias_analysis_evaluation_prompt)
    print("=== Completed result and bias analysis evaluation ===")

    # Parse and save all evaluation results
    print("=== Parsing and saving all evaluation results ===")
    all_evaluation_data = {
        "analysis_evaluation": parse_and_save_evaluation_data(analysis_evaluation_results[0]),
        "modeling_rigorousness_evaluation": parse_and_save_evaluation_data(modeling_rigorousness_evaluation_results[0]),
        "practicality_and_scientificity_evaluation": parse_and_save_evaluation_data(practicality_and_scientificity_evaluation_results[0]),
        "result_and_bias_analysis_evaluation": parse_and_save_evaluation_data(result_and_bias_analysis_evaluation_results[0])
    }

    # Save all evaluation results to JSON file
    print(f"=== Saving all evaluation results to {evaluation_results_json_path} ===")
    with open(evaluation_results_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_evaluation_data, f, ensure_ascii=False, indent=2)

    print(f"All evaluation results saved to {evaluation_results_json_path}")

    # Concatenate all evaluation results and save to .txt file
    print(f"=== Concatenating all evaluation results and saving to {evaluation_results_txt_path} ===")
    all_evaluation_results = (
        analysis_evaluation_results[0] + "\n\n" +
        modeling_rigorousness_evaluation_results[0] + "\n\n" +
        practicality_and_scientificity_evaluation_results[0] + "\n\n" +
        result_and_bias_analysis_evaluation_results[0]
    )

    with open(evaluation_results_txt_path, 'w', encoding='utf-8') as f:
        f.write(all_evaluation_results)

    print(f"All evaluation results saved to {evaluation_results_txt_path}")
    print("=== Evaluation completed ===")


def main(args):
    llm =  partial(gpt, base_url=args.base_url, key=args.key, model='gpt-4o', temperature=0.7, max_tokens=4000)
    solution_dir = args.solution_dir
    
    for file_name in os.listdir(solution_dir):
        if file_name.endswith(".json"):
            solution_file = os.path.join(solution_dir, file_name)
            if os.path.isfile(solution_file):
                evaluate_math_modeling(llm, solution_file)
    

def calculate_average_scores(args):
    baseline_path = args.baseline_path
    
    # metrics
    metrics = {
        "analysis_evaluation": [],
        "modeling_rigorousness_evaluation": [],
        "practicality_and_scientificity_evaluation": [],
        "result_and_bias_analysis_evaluation": []
    }

    for dir_name in [name for name in os.listdir(baseline_path) if os.path.isdir(os.path.join(baseline_path, name))]:
        evaluation_dir = os.path.join(baseline_path, dir_name)
        if os.path.exists(evaluation_dir):
            for dir in os.listdir(evaluation_dir):
                for file_name in os.listdir(os.path.join(evaluation_dir, dir)):
                    if file_name.endswith(".json"):
                        evaluation_file = os.path.join(evaluation_dir, dir, file_name)
                        if os.path.isfile(evaluation_file):
                            with open(evaluation_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                for key in metrics.keys():
                                    if key in data:
                                        for analysis in data[key].values():
                                            metrics[key].append(analysis["score"])

    # Calculate the average
    average_scores = {key: (sum(scores) / len(scores) if scores else 0) for key, scores in metrics.items()}
    print("=== Average Score ===")
    for key, avg_score in average_scores.items():
        print(f"{key}: {avg_score:.2f}")

    return average_scores


def visualization(baseline_path):
    results = []
    args = argparse.Namespace(baseline_path=baseline_path, evaluation_model='gpt-4o', temp=0.7, max_tokens=4000)
    avg_scores = calculate_average_scores(args)
    baseline_name = os.path.basename(os.path.normpath(baseline_path))
    results.append((baseline_name, avg_scores))
    
    # Printing Markdown-formatted tables
    headers = ["Baseline", "Analysis Evaluation", "Modeling Rigorousness", "Practicality and Scientificity", "Result and Bias Analysis"]
    print("| " + " | ".join(headers) + " |")
    print("|" + " --- |" * len(headers))
    
    for baseline_name, avg_scores in results:
        row = [baseline_name] + [f"{avg_scores[metric]:.2f}" for metric in avg_scores]
        print("| " + " | ".join(row) + " |")


if __name__ == '__main__':
     
    parser = argparse.ArgumentParser(description="Evaluate math modeling solutions.")
    parser.add_argument('--solution_dir', type=str, default="MMBench/example_solution/", help='Path to the directory containing solution files.')
    parser.add_argument('--evaluation_model', type=str, default='gpt-4o', help='Model to use for evaluation.')
    parser.add_argument('--temp', type=float, default=0.7, help='Temperature setting for the model.')
    parser.add_argument('--max_tokens', type=int, default=4000, help='Maximum number of tokens for the model.')
    parser.add_argument('--base_url', type=str, default="https://api.openai.com/v1")
    parser.add_argument('--key', type=str, default='')

    args = parser.parse_args()

    main(args)
    visualization(args.solution_dir)
