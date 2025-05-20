# MM-Bench: A Mathematical Modeling Benchmark

**MM-Bench** is a benchmark designed for evaluating mathematical modeling agents and systems. It is constructed based on problems from the Mathematical Contest in Modeling (MCM) and Interdisciplinary Contest in Modeling (ICM) spanning the years 2000–2025. The benchmark supports evaluation of agent capabilities across a diverse set of real-world problem domains.

## 📁 Folder Structure

MM-Bench contains the following four directories:

### 1. `problem/`

* Includes **111 mathematical modeling problems** from the MCM/ICM competitions (2000–2025).
* Each problem is stored in JSON format and contains the following fields:

  * `background`: The background information of the modeling problem.
  * `problem_requirement`: The specific questions and requirements to be addressed.
  * `dataset_path`: Path to the associated dataset (if available).
  * `dataset_description`: Description of the provided dataset.
  * `variable_description`: Description of the dataset's variables and fields.
  * `addendum`: Additional information or clarifications (if any).

### 2. `dataset/`

* Contains the datasets associated with the MCM/ICM problems from 2000–2025.
* Datasets are used to support empirical modeling.

### 3. `evaluation/`

* Includes the evaluation script for assessing agent outputs on MM-Bench problems.
* You can evaluate a single solution or a directory of solutions.

#### ✅ Evaluate a single solution:

```bash
python MMBench/evaluation/run_evaluation.py --solution_file_path "your_solution_file_path" --key "your_openai_key"
```

Example:

```bash
python MMBench/evaluation/run_evaluation.py --solution_file_path "MMBench/example_output/example1.json" --key "sk-XXX"
```

#### ✅ Evaluate all solutions in a folder:

```bash
python MMBench/evaluation/run_evaluation_batch.py --solution_dir "your_solution_dir" --key "your_openai_key"
```

Example:

```bash
python MMBench/evaluation/run_evaluation_batch.py --solution_dir "MMBench/example_output" --key "sk-XXX"
```

### 4. `example_solution/`

* Contains two examples of agent's solutions in response to problems from MM-Bench.

## 📌 Notes

* This benchmark is particularly suitable for evaluating LLM-based mathematical modeling agents.
* The dataset and problem structures are designed to support analysis, modeling, and code generation tasks.
* Please cite appropriately if you use MM-Bench in academic or applied research.