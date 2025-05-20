import json
import re

def generate_problem_analysis_prompt(solution_data: dict):
    """
    Generate a prompt focused on evaluating problem analysis and understanding.

    Args:
        problem_data (dict): Data loaded from problem.json, containing 'background', 'problem', and 'requirements'.
        solution_data (dict): Data loaded from solution.json, each task containing 'task_analysis'.
        
    Returns:
        str: Problem analysis and understanding evaluation prompt.
    """
    # Extract information from problem.json
    background = solution_data.get('background', 'None')
    requirements = solution_data.get("problem_requirement", [])
    
    # Extract all task_analysis and label them as Task 1, Task 2, etc.
    task_analyses = []
    task_number = 1
    for task_key, task in solution_data.items():
        task_analysis = task.get("task_description", '').strip()
        if task_analysis:
            task_analyses.append(f"**Task {task_number}**: {task_analysis}")
        else:
            task_analyses.append(f"**Task {task_number}**: No task analysis content.")
        task_number += 1
    
    # Combine all task_analysis into one paragraph
    all_task_analyses = "\n\n".join(task_analyses)
    
    # Generate evaluation prompt
    prompt = f"""
Your task is to evaluate the rationality and overall coherence of the problem decomposition into sub-problems by the modeler, given the backgroud and problem requirement  in mathematical modeling.

**Background**:
{background}

**Problem Requirements**:
{requirements}

Below is the modeler's task analysis:
**Task Analysis**:
{all_task_analyses}

**Evaluation Criteria**:
### 1. Problem Analysis and Understanding

#### 1.1 Problem Definition and Goals
Ensure the model definition is clear, the analysis is accurate, and the goals are explicit.
- Is the scope and goal of the problem clearly defined?
- Are the key components of the problem effectively identified?
- Are the actual goals that the model aims to solve clearly stated?

**Scoring Criteria**:
1-2 = Completely unclear; 3-4 = Not clear enough; 5-6 = Basically clear; 7-8 = Clear; 9-10 = Completely clear.

#### 1.2 Relevant Scope and Coverage
Ensure that the core part of the problem is not deviated from, and whether each sub-task is interrelated and completely covers the actual goals.
- Do the sub-tasks have dependencies?
- Are all sub-tasks and steps directly related and support the final goal?
- Are there any key parts missing or deviations from the actual goals?

**Scoring Criteria**:
1-2 = Completely deviated from the goal; 3-4 = Partially deviated; 5-6 = Basically covered; 7-8 = Mostly covered; 9-10 = Completely covered.

**Output Format**: Please put your evaluation reasons and scores in the tags <reason> your_reason </reason>, and <score> your_score </score>.
Example:
### 1.1 Problem Definition and Goals: \n\n**Evaluation:**\n\nThe modeler has provided a clear definition of the problem and its goals. However, there are some areas that need further clarification, such as the specific metrics used to measure success and the assumptions made during the analysis. Overall, the problem definition is mostly clear but could benefit from additional detail.
**Score:**\n<reason> The problem definition is mostly clear but lacks some details </reason>  \n<score> 7 </score>  
### 1.2 Relevant Scope and Coverage: \n\n**Evaluation:**\n\nThe sub-tasks are well-defined and cover the main aspects of the problem. There is a logical flow between the tasks, and each task supports the overall goal. However, some sub-tasks could be more detailed to ensure complete coverage of the problem.
**Score:**\n<reason> The sub-tasks are well-defined but could be more detailed </reason>  \n<score> 8 </score>

Please objectively and detailedly evaluate the problem analysis and understanding according to the above evaluation criteria, and give the final score and reason.
### 1.1 Problem Definition and Goals:
"""
    return prompt.strip()

def generate_modeling_rigorousness_prompt(solution_data: dict):
    """
    Generate a prompt focused on evaluating the rigor and rationality of modeling.

    Args:
        modeling_analysis (dict): Data loaded from solution.json, each task containing 'modeling_analysis'.
        
    Returns:
        str: Evaluation prompt for the rigor and rationality of modeling.
    """
    # Extract information from problem.json
    background = solution_data.get('background', 'None')
    requirements = solution_data.get("problem_requirement", [])

    # Extract all modeling_analysis and label them as Task 1, Task 2, etc.
    task_analyses = []
    task_number = 1
    for task_key, task in solution_data.items():
        task_analysis = task.get("task_analysis", '').strip()
        if task_analysis:
            task_analyses.append(f"**Task {task_number}**: {task_analysis}")
        else:
            task_analyses.append(f"**Task {task_number}**: No task analysis content.")
        task_number += 1
    
    # Combine all task_analysis into one paragraph
    all_task_analyses = "\n\n".join(task_analyses)
    
    # Generate evaluation prompt
    prompt = f"""
Your task is to evaluate the rigor and rationality of the modeling given the backgroud and problem requirement in mathematical modeling, particularly focusing on the assumptions and rationality.

**Background**:
{background}

**Problem Requirements**:
{requirements}

Below is the modeler's modeling analysis:
**Modeling Analysis**:
{all_task_analyses}

**Evaluation Criteria**:
### 2. Rigor and Rationality of Modeling

#### 2.1 Assumptions
Clear and explicit. These assumptions are the foundation of the model and need to be rigorously justified.
- Are the model assumptions clearly explained?
- Are the assumptions reasonable and consistent with the background of the actual problem?
- Is the rationality and impact of the assumptions considered?

**Scoring Criteria**:
1-2 = Completely unreasonable; 3-4 = Partially reasonable; 5-6 = Average; 7-8 = Reasonable; 9-10 = Very reasonable.

#### 2.2 Rationality
The rationality of the model is key to evaluation. Evaluation criteria can include: whether an appropriate model is chosen, whether the model can realistically reflect the problem, etc.
- Has the model chosen appropriate methods and metrics?
- Does the structure of the model scientifically reflect the actual problem?

**Scoring Criteria**:
1-2 = Completely unreasonable; 3-4 = Partially reasonable; 5-6 = Average; 7-8 = Reasonable; 9-10 = Very reasonable.

**Output Format**:
Example:
### 2.1 Assumptions\n\n**Evaluation:**\n\nThe assumptions are crucial for model building, but the modeling analysis does not describe the assumptions in sufficient detail. The rationality and impact of the assumptions are not fully justified, lacking detailed explanations of data sources, data distribution, and competition characteristics. For example, the assumption about "serve advantage" is mentioned but not detailed on how it is quantified and integrated into the model. Additionally, the assumptions are not clearly explained, making the foundation of the model less robust.
**Score:**\n<reason> The model assumptions are not clear enough and lack sufficient explanation of their sources and impacts </reason>  \n<score> 3 </score>  
### 2.2 Rationality \n\n**Evaluation:**\n\nThe rationality of the model is average. The modeler chose to evaluate player performance based on match data (such as points won, games won, and sets won), which is reasonable to some extent. However, the specific modeling methods and metrics are not detailed. For example, how to quantify "performance score", how to handle time series data, and whether psychological factors in the competition are considered. Although some possible methods (such as time series analysis, regression, or classification) are mentioned, their specific applications and reasons for selection are not deeply explained. The structure of the model may have certain limitations in reflecting the actual problem.
**Score:**\n<reason> The rationality of the model is average, with methods and metrics not detailed, and the model structure has limitations </reason>  \n<score> 5 </score>

Please objectively and detailedly evaluate the rigor and rationality of the modeling according to the above evaluation criteria, and give the final score and reason.
### 2.1 Assumptions\n\n**Evaluation:
"""
    return prompt.strip()

def generate_practicality_and_scientificity_prompt(solution_data: dict):
    """
    Generate a prompt focused on evaluating the practicality and scientificity of the modeling process.

    Args:
        problem_data (dict): Data loaded from problem.json, containing problem description, background information, and existing requirements.
        solution_data (dict): Data loaded from solution.json, containing the modeling analysis for each task.
        
    Returns:
        str: Evaluation prompt for the practicality and scientificity of the modeling process.
    """
    background = solution_data.get('background', 'None')
    requirements = solution_data.get("problem_requirement", [])

    # Extract all modeling_analysis and label them as Task 1, Task 2, etc.
    task_analyses = []
    task_number = 1
    for task_key, task in solution_data.items():
        task_analysis = task.get("mathematical_modeling_process", '').strip()
        if task_analysis:
            task_analyses.append(f"**Task {task_number}**: {task_analysis}")
        else:
            task_analyses.append(f"**Task {task_number}**: No task analysis content.")
        task_number += 1
    
    # Combine all task_analysis into one paragraph
    all_task_analyses = "\n\n".join(task_analyses)
    
    # Generate evaluation prompt
    prompt = f"""
Your task is to evaluate the practicality and scientificity of the modeling process given the background and problem requirements in mathematical modeling, particularly focusing on whether the model can practically solve the problem and whether it adheres to scientific principles.

**Background**:
{background}

**Problem Requirements**:
{requirements}

Below is the modeler's modeling process:
**Modeling Process**:
{all_task_analyses}

**Evaluation Criteria**:
### 3. Practicality and Scientificity

#### 3.1 Practicality
- Does the modeling method match the characteristics and requirements of the problem?
- Does the model provide meaningful insights beyond mere data fitting? Can its output support decision-making with clear explanations and reliable predictions across different datasets?  
- Does the approach go beyond standard machine learning or data processing? Has it been deeply optimized or extended, potentially integrating interdisciplinary methods like mathematical or physical modeling?  
- Does the model introduce novel frameworks, constraints, objectives, or data representations? Does it push beyond conventional techniques to propose new theoretical or computational approaches?  
- Is the selected modeling method appropriate for the given problem?
- Is the model reasonably constructed?
- Can the model solve the actual problem?
- Are the application scenarios of the model clear? Is it feasible for practical operation?
- Can the model's output provide useful information for decision-making or exaplaining or predcting?
- Does the approach go beyond basic data analysis and machine learning algorithms?
- Does the model demonstrate innovation or creativity in its approach to addressing the problem?
- Is the modeling approach tailored to the specific problem rather than using generic methods?

**Scoring Criteria**:
1-2 = Completely impractical; 3-4 = Partially practical; 5-6 = Average; 7-8 = Practical; 9-10 = Very practical.

#### 3.2 Scientificity
- Does the model adhere to scientific principles? Is there a theoretical basis?
- Are the assumptions and methods of the model scientifically justified?
- Does the model consider all scientific factors to ensure its rationality?
- Does the approach transcend simple data analysis to incorporate deeper mathematical or domain-specific principles?
- Is the approach innovative rather than a standard application of common techniques?
- Does the modeling process demonstrate understanding of the problem's unique characteristics?

**Scoring Criteria**:
1-2 = Completely unscientific; 3-4 = Partially scientific; 5-6 = Average; 7-8 = Scientific; 9-10 = Very scientific.

**Output Format**:
Example:
### 3.1 Practicality\n\n**Evaluation:**\n\nThe model is somewhat practical, but it lacks several key aspects. The modeling method does not fully match the characteristics and requirements of the problem. Additionally, the model does not provide meaningful insights beyond mere data fitting, and its output lacks clear explanations and reliable predictions across different datasets. The approach does not go beyond standard machine learning or data processing, and it has not been deeply optimized or extended to integrate interdisciplinary methods like mathematical or physical modeling. Furthermore, the model does not introduce novel frameworks, constraints, objectives, or data representations, and it does not push beyond conventional techniques to propose new theoretical or computational approaches.
**Score:**\n<reason> The model lacks several key aspects, including matching the problem characteristics, providing meaningful insights, and introducing novel approaches </reason> \n<score> 6 </score>  

### 3.2 Scientificity\n\n**Evaluation:**\n\nThe model adheres to clear scientific principles and employs reasonable theoretical foundations. The assumptions and methods are scientifically justified, and the modeler has thoroughly explained the rationality of the assumptions. Rather than relying solely on basic data analysis techniques, the approach incorporates sophisticated mathematical principles and demonstrates innovative application of theoretical concepts to the specific domain of the problem.
**Score:**\n<reason> The model adheres to scientific principles, incorporates advanced mathematical concepts, and demonstrates innovative application rather than generic approaches </reason> \n<score> 7 </score>

Please objectively and detailedly evaluate the practicality and scientificity of the modeling process according to the above evaluation criteria, and provide the final score and reason.
### 3.1 Practicality\n\n**Evaluation:
"""
    return prompt.strip()


def generate_result_and_bias_analysis_prompt(solution_data: dict):
    """
    Generate a prompt focused on evaluating the result analysis and bias analysis of the modeling.

    Args:
        problem_data (dict): Data loaded from problem.json, containing problem description, background information, and existing requirements.
        solution_data (dict): Data loaded from solution.json, containing the modeling analysis for each task.
        
    Returns:
        str: Result analysis and bias analysis evaluation prompt.
    """
    # Extract problem description, background, and requirements

    background = solution_data.get('background', 'None')
    requirements = solution_data.get("problem_requirement", [])

    # Extract all modeling_analysis and label them as Task 1, Task 2, etc.
    task_analyses = []
    task_number = 1
    for task_key, task in solution_data.items():
        answer_analysis = task.get("subtask_outcome_analysis", task.get("answer", '')).strip()
        if answer_analysis:
            task_analyses.append(f"**Task {task_number}**: {answer_analysis}")
        else:
            task_analyses.append(f"**Task {task_number}**: No task analysis content.")
        task_number += 1
    
    # Combine all task_analysis into one paragraph
    all_task_analyses = "\n\n".join(task_analyses)
    
    # Generate evaluation prompt
    prompt = f"""
Your task is to evaluate the result analysis and bias analysis of the given modeling report, particularly focusing on the rationality, interpretability of the model output, and the identification and correction of biases.

**Background**:
{background}

**Problem Requirements**:
{requirements}

Below is the modeler's modeling report:
**Modeling Report**:
{all_task_analyses}

**Evaluation Criteria**:
### 4. Result Analysis and Bias Analysis

#### 4.1 Result Analysis
- Are the model output results clear and as expected?
- Does the result provide sufficient analysis to explain the model's inference process?
- Are the model results interpretable and do they help in understanding the essence of the problem?
- Does the analysis provide clear conclusions and highlight the strengths and weaknesses of the model?

**Scoring Criteria**:
1-2 = Completely unclear; 3-4 = Partially clear; 5-6 = Average; 7-8 = Clear; 9-10 = Very clear.

#### 4.2 Bias Analysis
- Does the model identify and analyze potential biases?
- Does it consider data bias, model bias, and other factors?
- Does the model appropriately correct biases to reduce their impact on the results?

**Scoring Criteria**:
1-2 = Completely ignored biases; 3-4 = Partially considered biases; 5-6 = Average; 7-8 = Considered biases and corrected; 9-10 = Very thorough, biases effectively corrected.

**Output Format**:
Example 1:
### 4.1 Result Analysis\n\n**Evaluation:**\n\nThe model output results are clear and well explain the model's inference process. The modeler has detailed the background and significance of the model results, helping to understand the core of the problem. The results show a reasonable inference path, making the entire analysis process more transparent. The analysis also provides clear conclusions and highlights the strengths and weaknesses of the model.
**Score:**\n<reason> The result analysis is very clear and effectively supports decision-making </reason> \n<score> 9 </score>  

### 4.2 Bias Analysis\n\n**Evaluation:**\n\nThe model effectively identifies and analyzes biases, particularly potential data biases. The modeler provides correction measures for biases and explains how these corrections affect the model results. Although there are still some biases in certain aspects of the model, overall, a comprehensive correction has been made.
**Score:**\n<reason> The bias analysis is thorough, and biases have been effectively corrected </reason> \n<score> 8 </score>

Please objectively and detailedly evaluate the result analysis and bias analysis of the modeling according to the above evaluation criteria, and provide the final score and reason.
### 4.1 Result Analysis\n\n**Evaluation:
"""
    return prompt.strip()