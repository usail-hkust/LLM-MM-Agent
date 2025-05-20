PROBLEM_PROMPT = """\
Problem Background:
{problem_background}

Problem Requirement:
{problem_requirement}
{addendum}
{data_summary}
"""


DATA_DESCRIPTION_PROMPT = """\
Data Description:
{data_description}

---

Your task is to generate a detailed summary of the dataset based on the dataset description provided. It needs to cover comprehensive information, but not explain each field one by one. Using plain text to describe in a single paragraph, without any Markdown formatting or syntax.
"""


PROBLEM_ANALYSIS_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

---

You are tasked with analyzing a mathematical modeling problem with a focus on the underlying concepts, logical reasoning, and assumptions that inform the solution process. Begin by considering the nature of the problem in its broader context. What are the primary objectives of the model, and how do they shape the way you approach the task? Think critically about the assumptions that may be inherently embedded in the problem. What implicit beliefs or constraints have been set up, either explicitly or implicitly, within the problem’s description? Reflect on how these assumptions might influence the interpretation and application of any potential solutions. 

Dive deeper into the relationships and interdependencies between the different components of the problem. What are the potential hidden complexities that may arise from these interconnections? Are there any conflicts or tensions between different aspects of the problem that need to be resolved? Explore how these interdependencies might lead to unforeseen challenges and require revisiting initial assumptions or redefining the parameters of the task. 

Consider how the complexity of the problem may evolve across different scales or over time. Are there time-dependent factors or long-term consequences that should be accounted for, especially in terms of the stability or sustainability of the model’s outcomes? Think about how the model’s behavior might change under different scenarios, such as variations in input or changes in external conditions. Reflect on whether any simplifications or idealizations in the problem might inadvertently obscure key dynamics that are crucial for an accurate representation.

In your analysis, also give attention to possible alternative perspectives on the problem. Are there different ways to frame the issue that could lead to distinct modeling approaches or solution strategies? How would those alternative perspectives impact the overall approach? Additionally, evaluate the potential risks or uncertainties inherent in the problem, especially when it comes to choosing between competing modeling approaches. Consider how the outcomes might vary depending on the choices you make in constructing the model, and how you would manage such trade-offs.

Finally, reflect on the dynamic nature of the modeling process itself. How might your understanding of the problem evolve as you continue to explore its intricacies? Ensure that your thought process remains flexible, with a readiness to revise earlier conclusions as new insights emerge. The goal is to maintain a reflective, iterative analysis that adapts to deeper understandings of the task at hand, rather than pursuing a fixed or rigid approach.

{user_prompt}

Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


PROBLEM_ANALYSIS_CRITIQUE_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

---

Critically examine the analysis results of the given mathematical modeling problem, focusing on the following aspects:

1. Depth of Thinking: Evaluate whether the analysis demonstrates a comprehensive understanding of the underlying problem. Does it go beyond surface-level observations? Are the assumptions, limitations, and potential implications of the results carefully considered? Assess whether the analysis adequately addresses both the broader context and specific intricacies of the problem.
2. Novelty of Perspective: Analyze the originality of the approach taken in the analysis. Does it introduce new insights or merely rehash well-established methods or solutions? Are alternative perspectives or unconventional techniques explored, or is the analysis constrained by a narrow set of assumptions or typical approaches?
3. Critical Evaluation of Results: Consider the extent to which the analysis critically engages with the results. Are the conclusions drawn from the analysis well-supported by the mathematical findings, or do they overlook key uncertainties or counterexamples? Does the analysis acknowledge potential contradictions or ambiguities in the data?
4. Rigor and Precision: Assess the level of rigor applied in the analysis. Are the steps logically consistent and mathematically sound, or are there overlooked errors, gaps, or assumptions that undermine the conclusions? Does the analysis exhibit a clear, methodical approach, or is it characterized by vague reasoning and imprecision?
5. Contextual Awareness: Evaluate how well the analysis situates itself within the broader landscape of mathematical modeling in this area. Does it consider previous work or developments in the field? Is there any indication of awareness of real-world implications, practical constraints, or ethical concerns, if applicable?

Critique the analysis without offering any constructive suggestions—your focus should solely be on highlighting weaknesses, gaps, and limitations within the approach and its execution.
"""


PROBLEM_ANALYSIS_IMPROVEMENT_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

# Problem Analysis Critique:
{problem_analysis_critique}

---

Refine and improve the existing problem analysis based on the critique provided to generate insightful analysis. 

Provide the improved version directly. DO NOT mention any previous analysis content and deficiencies in the improved analysis. Just refer to the above critical suggestions and directly give the new improved analysis.
{user_prompt}
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.

IMPROVED PROBLEM ANALYSIS:
"""


METHOD_CRITIQUE_PROMPT = """\
## Problem Description

{problem_description}

## Method List

{methods}

## Evaluation Task

Evaluate each method based on the following dimensions. For each dimension, consider the associated criteria and assign a score from 1 (poor) to 5 (excellent). 

## Criteria Dimensions

**1. Assumptions:** Whether the foundational mathematical assumptions align with the intrinsic characteristics of the problem.  
For instance, linear regression assumes linear relationships but fails to capture nonlinear dynamics (e.g., exponential growth). Similarly, deterministic models (e.g., ordinary differential equations) may overlook critical uncertainties in inherently stochastic systems (e.g., financial markets or biological processes). Misaligned assumptions risk oversimplification or systematic bias.

**2. Structure:** The mathematical framework’s ability to mirror the problem’s inherent logic, hierarchy, or spatiotemporal relationships.  
Network-based problems (e.g., traffic flow or social interactions) demand graph theory or network flow models, while hierarchical systems (e.g., ecological food webs) may require multi-stage or layered modeling. A mismatch here—such as using static equations for time-dependent phenomena—renders the model structurally inadequate.

**3. Variables:** Compatibility between the model’s mathematical tools and the variable types in the problem (continuous, discrete, categorical, stochastic, etc.).  
For example, logistic regression or decision trees suit categorical outcomes, while partial differential equations better model spatially continuous systems. High-dimensional sparse data (e.g., genomics) may necessitate dimensionality reduction (PCA) or sparse optimization, whereas rigid variable handling leads to inefficiency or inaccuracy.

**4. Dynamics:** Alignment of the model’s temporal or dynamic properties with the problem’s evolutionary behavior.  
Short-term forecasting might use static models (e.g., linear regression), but long-term ecological or economic systems require dynamic frameworks (e.g., differential equations or agent-based models). Ignoring time delays (e.g., policy impacts in economics) or feedback loops often invalidates predictions.

**5. Solvability:** The existence and practicality of solutions under real-world constraints.  
High-dimensional non-convex optimization problems (e.g., neural network training) may rely on heuristic algorithms (genetic algorithms) rather than exact solutions. Similarly, NP-hard problems (e.g., traveling salesman) demand approximations to balance computational feasibility and precision. Overly complex models risk theoretical elegance without actionable results.

## Instructions
1. For each method in the Method List, score its performance on **all** evaluation dimensions.
2. Return results in JSON format, including the method index and scores for each dimension.

## Output Example (Only return the JSON output, no other text)
```json
{{
  "methods": [
    {{
      "method_index": 1,
      "scores": {{
        "Assumptions": 4,
        "Structure": 3,
        // Include other dimensions here
      }}
    }},
    // Include other methods here
  ]
}}
```

## Required Output
Provide the JSON output below:
```json
"""


PROBLEM_MODELING_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

---

You are tasked with designing an innovative mathematical model to address the given problem. Begin by proposing a comprehensive model that integrates both theoretical and practical considerations, ensuring that the formulation is aligned with the problem's core objectives. This should include a clear set of assumptions that underpin the model, which may involve simplifications, approximations, or idealizations necessary to make the problem tractable, yet still retain fidelity to the real-world phenomena you aim to represent. Clearly define the variables, parameters, and constraints that will shape the mathematical formulation. 

Next, develop the key equations and relationships that will govern the model. Pay attention to the interdependencies between the various components of the system. These could involve differential equations, algebraic relations, optimization criteria, or probabilistic models, depending on the nature of the problem. Be sure to consider how different aspects of the model might interact, and whether feedback loops or non-linearities should be incorporated. Explore potential novel formulations or extensions of existing models that could offer new insights into the problem's dynamics. If applicable, propose advanced methods such as multi-scale modeling, agent-based simulations, or data-driven approaches like machine learning to improve the model’s adaptability or accuracy.

Once the model structure is established, outline a clear strategy for solving it. This may involve analytical techniques such as closed-form solutions or approximations, numerical methods like finite element analysis or Monte Carlo simulations, or optimization algorithms for parameter estimation. Be explicit about the computational resources required and the level of precision expected. If the model is complex or high-dimensional, suggest ways to reduce the computational burden, such as dimensionality reduction, surrogate models, or parallelization techniques. 

Additionally, consider how the model might evolve over time or under different conditions. Would the model require recalibration or adaptation in the face of changing circumstances? If applicable, provide strategies for sensitivity analysis to assess how the model responds to changes in its assumptions or parameters. Reflect on how the model’s predictions can be validated through empirical data or experimental results, ensuring that the model provides actionable insights and maintains real-world relevance.

Finally, propose avenues for further refinement or extension of the model. As new data becomes available or the problem context shifts, what adjustments would you make to improve the model's accuracy or applicability? Explore the possibility of incorporating new dimensions into the model, such as incorporating uncertainty quantification, dynamic optimization, or considering long-term sustainability of the proposed solutions. The ultimate goal is to develop a robust, flexible, and innovative model that not only addresses the problem at hand but also offers deeper insights into its underlying complexities.

{user_prompt}

Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


PROBLEM_MODELING_CRITIQUE_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

# Modeling Solution:
{modeling_solution}

---

Critically examine the analysis results of the given mathematical modeling solution, focusing on the following aspects:

1. Problem Analysis and Understanding:
- Clarity of the problem definition: Does the solution demonstrate a clear and comprehensive understanding of the problem? Are all relevant variables, constraints, and objectives identified and well-defined? If not, which aspects of the problem may have been misunderstood or overlooked?
- Contextualization and framing: How well does the model account for the context in which the problem is situated? Are there any contextual factors that are essential but were not addressed?
- Scope of the problem: Is the problem's scope appropriately defined? Does the model include all the necessary details, or are there significant components that were neglected or oversimplified?

2. Model Development and Rigor:
- Formulation of the mathematical model: How well is the model constructed mathematically? Does it align with established modeling practices in the relevant domain? Are the mathematical formulations—such as equations, algorithms, or optimization methods—correct and robust?
- Modeling techniques: What modeling approaches or techniques were used (e.g., linear programming, system dynamics, statistical modeling, etc.)? Are they the most appropriate for the problem at hand? What alternative approaches could have been considered, and how might they impact the solution?
- Validation and verification: Was the model tested for consistency and accuracy? Are there validation steps in place to ensure the model behaves as expected under a variety of conditions? What specific methods were used for this validation (e.g., cross-validation, sensitivity analysis, etc.)?

3. Data and Results Analysis:
- Data quality and relevance: Were there any significant issues with data availability or quality that could have influenced the model's results?
- Interpretation of results: How well were the results analyzed and interpreted? Were the outcomes consistent with the problem's real-world implications? Are there any discrepancies between the model’s results and known empirical observations?
- Sensitivity and robustness analysis: Did the model undergo a sensitivity analysis to determine how the results vary with changes in input parameters? Were the results robust across different assumptions, and if not, what are the implications for the solution's reliability?

4. Assumptions and Limitations:
- Explicit and implicit assumptions: What assumptions underlie the model, and are they clearly articulated? Are these assumptions reasonable, and how might they affect the model's predictions? Were any critical assumptions left implicit or unaddressed?
- Limitations of the model: What limitations are inherent in the model, and how do they affect its validity and reliability? Are there elements of the problem that are inherently difficult or impossible to model with the chosen approach? Were simplifications made, and what are the trade-offs involved?
- Model boundaries: Does the model appropriately define its boundaries, and are there any critical factors that lie outside the model’s scope but could significantly influence the results?

5. Practicality and Applicability:
- Real-world applicability: To what extent can the model be applied to real-world scenarios? 
- Practical implementation: How would this model be implemented in practice? What would be the required infrastructure, and what challenges would need to be addressed during implementation? 

Critique the analysis without offering any constructive suggestions—your focus should solely be on highlighting weaknesses, gaps, and limitations within the approach and its execution.
"""


PROBLEM_MODELING_IMPROVEMENT_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

# Modeling Solution:
{modeling_solution}

# Modeling Solution Critique:
{modeling_solution_critique}

---

Refine and improve the existing modeling solution based on the critique provided. The goal is to enhance the formulation, structure, and overall effectiveness of the model while addressing the identified gaps, flaws, or limitations. Propose more appropriate assumptions, more robust mathematical techniques, or alternative modeling approaches if necessary. Focus on improving the model's relevance, accuracy, and computational feasibility while also ensuring its ability to capture the complexity of the problem in real-world contexts.

Provide a new version of the modeling solution that integrates these improvements directly. DO NOT mention any previous solution content and deficiencies.

{user_prompt}

Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.

IMPROVED MODELING SOLUTION: 
"""


DECOMPOSE_PRINCIPLE_PROMPT = """\
The solution to a mathematical modeling problem is typically broken down into a series of subtasks, each addressing a different aspect of the overall challenge. Based on the examples provided below, summarize what each subtask in tasks 1 through {tasknum} generally involves, with a focus on the principles of task decomposition in mathematical modeling.

<examples>

{examples}

</examples>

Requirements:
1. The summary should focus on the general methods and approaches used in mathematical modeling tasks, not tied to any specific examples or cases provided.
2. The response should not include any details specific to the examples in order to avoid providing any implicit solutions or insights from them.
3. The summary should present a theoretical description of the techniques used at each stage of task decomposition, without any reference to particular problems or contexts.
4. Each subtask should be described as comprehensively and in as much detail as possible within a single paragraph, capturing the essential steps and considerations for that task in a general mathematical modeling framework. The description should be comprehensive, highlighting the key methodologies without resorting to bullet points, numbered lists, or overly formalized structure.
5. Do not provide any form of examples or mention any instances.
"""


TASK_DECOMPOSE_PROMPT = """\
# Decompose Principle:
{decomposed_principle}

# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

# Modeling Solution:
{modeling_solution}

---

Please decompose the given modeling solution into {tasknum} distinct and well-defined subtasks that collectively contribute to the overall objective. These subtasks should be clearly separated in their focus, each addressing a specific aspect of the modeling process. The goal is to break down the solution into key stages or methodologies, ensuring that all components of the solution are covered without redundancy. For each subtask, the approach or technique should be explicitly described, detailing the specific data, algorithms, or models required. The decomposition should reflect a logical and comprehensive path toward completing the task, with each part having a clear purpose and contributing to the final result.
{user_prompt}
Each subtask should be described as comprehensively and in as much detail as possible within a single paragraph using plain text and seperated by '---' for each subtask. All the contents and details of the original solution need to be covered by the {tasknum} subtasks without omission. 
"""


TASK_DESCRIPTION_PROMPT = """\
# Mathematical Modeling Problem:
{modeling_problem}

# Problem Analysis:
{problem_analysis}

# Modeling Solution:
{modeling_solution}

# Decomposed Subtasks:
{decomposed_subtasks}

---

You are tasked with refining and improving the description of subtask {task_i} to ensure it is more detailed, clear, and focused. Provide a precise and comprehensive explanation of the task, specifically elaborating on its scope, goals, and methodology without venturing into other subtasks. Make sure the description includes clear and concise language that defines the necessary steps, techniques, or approaches required for this subtask. If applicable, specify the data inputs, tools, or models to be used, but do not introduce analysis, results, or discussions related to other components of the modeling process. The goal is to enhance the clarity, depth, and precision of this subtask description, ensuring it is fully understood on its own without needing further explanation.
The description of subtask {task_i} should be as comprehensive and in as much detail as possible within a single paragraph using plain text.
"""

TASK_ANALYSIS_PROMPT = """\
# Task Description:
{task_description}

---
{prompt}

You are collaborating as part of a multi-agent system to solve a complex mathematical modeling problem. Each agent is responsible for a specific task, and some preprocessing or related tasks may have already been completed by other agents. It is crucial that you **do not repeat any steps that have already been addressed** by other agents. Instead, rely on their outputs when necessary and focus solely on the specific aspects of the task assigned to you.

Provide a thorough and nuanced analysis of the task at hand, drawing on the task description as the primary source of context. Begin by elucidating the core objectives and scope of the task, outlining its significance within the larger context of the project or research. Consider the potential impact or outcomes that are expected from the task, whether they relate to solving a specific problem, advancing knowledge, or achieving a particular practical application. Identify any challenges that may arise during the task execution, including technical, logistical, or theoretical constraints, and describe how these might influence the process or outcomes. In addition, carefully highlight any assumptions that are being made about the data, environment, or system involved in the task, and discuss any external factors that could shape the understanding or execution of the task. Ensure that the analysis is framed in a way that will guide future steps or inform the next stages of work.
{user_prompt}
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text and LaTeX for formulas only, without any Markdown formatting or syntax. Written as one paragraph. Avoid structuring your answer in bullet points or numbered lists.
"""

TASK_FORMULAS_PROMPT = """\
# Reference Modeling Methods:
{modeling_methods}

{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

---
{prompt}

You are collaborating as part of a multi-agent system to solve a complex mathematical modeling problem. Each agent is responsible for a specific task, and some preprocessing or related tasks may have already been completed by other agents. It is crucial that you **do not repeat any steps that have already been addressed** by other agents. Instead, rely on their outputs when necessary and focus solely on the specific aspects of the task assigned to you.

You are tasked with developing a set of precise, insightful, and comprehensive mathematical formulas that effectively model the problem described in the task. Begin by conducting an in-depth analysis of the system, process, or phenomenon outlined, identifying all relevant variables, their interdependencies, and the fundamental principles, laws, or constraints that govern the behavior of the system, as applicable in the relevant field. Clearly define all variables, constants, and parameters, and explicitly state any assumptions, approximations, or simplifications made during the formulation process, including any boundary conditions or initial conditions if necessary.

Ensure the formulation considers the full scope of the problem, and if applicable, incorporate innovative mathematical techniques. Your approach should be well-suited for practical computational implementation, addressing potential numerical challenges, stability concerns, or limitations in simulations. Pay careful attention to the dimensional consistency and units of all terms to guarantee physical or conceptual validity, while remaining true to the theoretical foundations of the problem.

In the process of deriving the mathematical models, provide a clear, step-by-step explanation of the reasoning behind each formula, highlighting the derivation of key expressions and discussing any assumptions or trade-offs that are made. Identify any potential sources of uncertainty, limitations, or approximations inherent in the model, and provide guidance on how to handle these within the modeling framework.

The resulting equations should be both flexible and scalable, allowing for adaptation to different scenarios or the ability to be tested against experimental or real-world data. Strive to ensure that your model is not only rigorous but also interpretable, balancing complexity with practical applicability. List all modeling equations clearly in LaTeX format, ensuring proper mathematical notation and clarity of presentation. Aim for a model that is both theoretically sound and practically relevant, offering a balanced approach to complexity and tractability in its use.
{user_prompt}
Respond as comprehensively and in as much detail as possible, ensuring clarity, depth, and rigor throughout. Using plain text and LaTeX for formulas. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


TASK_FORMULAS_CRITIQUE_PROMPT = """\
{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

---

The goal of this task is to critically evaluate the modeling formulas used to represent a given mathematical modeling problem. Your analysis should address the following dimensions: accuracy and rigor, innovation and insight, and the applicability of the models to real-world scenarios.

1. Accuracy and Rigor:

- Formula Integrity:  
  Evaluate whether the mathematical models and the corresponding formulas are mathematically sound and consistent with the underlying assumptions of the problem. Are the formulas properly derived, free from logical errors, and reflective of the relevant domain knowledge?  
  - Are any simplifications or approximations made, and if so, are they justifiable within the context of the model's scope?
  - Examine the assumptions made in formulating the model. Are these assumptions realistic, and how do they affect the model’s precision and robustness?

2. Innovation and Insight:

- Novelty of Approach:  
  Critique the originality of the modeling approach. Does the model present a new or unconventional way of solving the problem, or does it simply rely on established methodologies without offering new insights?  
  - Consider whether any innovative methods, such as the introduction of novel variables or the use of innovative computational techniques, contribute to improving the model.

- Theoretical Insight:  
  Evaluate the depth of the theoretical insights provided by the model. Does it offer a fresh perspective or new understanding of the problem? How well does it illuminate the key dynamics and relationships within the system under study?  
  - Does the model reveal previously unnoticed phenomena, or does it suggest new directions for further research?

- Integration of Existing Knowledge:  
  Assess the extent to which the model integrates existing mathematical, theoretical, and empirical work. Does it build on prior research, and if so, does it do so in a way that adds substantial value or clarity? Are there gaps where additional cross-disciplinary knowledge could enhance the model?

---

3. Applicable:

- Real-World Relevance:  
  Evaluate the model’s practical applicability. How well does it apply to real-world problems, and to what extent does it provide actionable insights for decision-making or problem-solving in the field?  

Critique the analysis without offering any constructive suggestions—your focus should solely be on highlighting weaknesses, gaps, and limitations within the formulas.
"""


TASK_FORMULAS_IMPROVEMENT_PROMPT = """\
{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

# Task Modeling Formulas Critique:
{modeling_formulas_critique}

---

Based on the provided critique and analysis, refine the existing modeling formulas to address the identified limitations and gaps. 

Respond as comprehensively and in as much detail as possible, ensuring clarity, depth, and rigor throughout. Using plain text and LaTeX for formulas. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
{user_prompt}
Provide a new version of the task modeling formulas that integrates these improvements directly. DO NOT mention any previous formulas content and deficiencies.

IMPROVED TASK MODELING FORMULAS:
"""


TASK_MODELING_PROMPT = """\
{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

---
{prompt}

You are collaborating as part of a multi-agent system to solve a complex mathematical modeling problem. Each agent is responsible for a specific task, and some preprocessing or related tasks may have already been completed by other agents. It is crucial that you **do not repeat any steps that have already been addressed** by other agents. Instead, rely on their outputs when necessary and focus solely on the specific aspects of the task assigned to you.

Please continue the modeling formula section by building upon the previous introduction to the formula. Provide comprehensive and detailed explanations and instructions that elaborate on each component of the formula. Describe the modeling process thoroughly, including the underlying assumptions, step-by-step derivations, and any necessary instructions for application. Expand on the formula by incorporating relevant mathematical expressions where appropriate, ensuring that each addition enhances the reader’s understanding of the model. Make sure to seamlessly integrate the new content with the existing section, maintaining a natural flow and avoiding any repetition or conflicts with previously covered material. Your continuation should offer a clear and in-depth exploration of the modeling formula, providing all necessary details to facilitate a complete and coherent understanding of the modeling process.
{user_prompt}
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


TASK_MODELING_CRITIQUE_PROMPT = """\
{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

# Task Modeling Process:
{modeling_process}

---

Critically examine the analysis results of the given mathematical modeling solution, focusing on the following aspects:

1. Problem Analysis and Understanding:
- Clarity of the problem definition: Does the solution demonstrate a clear and comprehensive understanding of the problem? Are all relevant variables, constraints, and objectives identified and well-defined? If not, which aspects of the problem may have been misunderstood or overlooked?
- Contextualization and framing: How well does the model account for the context in which the problem is situated? Are there any contextual factors that are essential but were not addressed?
- Scope of the problem: Is the problem's scope appropriately defined? Does the model include all the necessary details, or are there significant components that were neglected or oversimplified?

2. Model Development and Rigor:
- Formulation of the mathematical model: How well is the model constructed mathematically? Does it align with established modeling practices in the relevant domain? Are the mathematical formulations—such as equations, algorithms, or optimization methods—correct and robust?
- Modeling techniques: What modeling approaches or techniques were used (e.g., linear programming, system dynamics, statistical modeling, etc.)? Are they the most appropriate for the problem at hand? What alternative approaches could have been considered, and how might they impact the solution?
- Validation and verification: Was the model tested for consistency and accuracy? Are there validation steps in place to ensure the model behaves as expected under a variety of conditions? What specific methods were used for this validation (e.g., cross-validation, sensitivity analysis, etc.)?

3. Data and Results Analysis:
- Data quality and relevance: Were there any significant issues with data availability or quality that could have influenced the model's results?
- Interpretation of results: How well were the results analyzed and interpreted? Were the outcomes consistent with the problem's real-world implications? Are there any discrepancies between the model’s results and known empirical observations?
- Sensitivity and robustness analysis: Did the model undergo a sensitivity analysis to determine how the results vary with changes in input parameters? Were the results robust across different assumptions, and if not, what are the implications for the solution's reliability?

4. Assumptions and Limitations:
- Explicit and implicit assumptions: What assumptions underlie the model, and are they clearly articulated? Are these assumptions reasonable, and how might they affect the model's predictions? Were any critical assumptions left implicit or unaddressed?
- Limitations of the model: What limitations are inherent in the model, and how do they affect its validity and reliability? Are there elements of the problem that are inherently difficult or impossible to model with the chosen approach? Were simplifications made, and what are the trade-offs involved?
- Model boundaries: Does the model appropriately define its boundaries, and are there any critical factors that lie outside the model’s scope but could significantly influence the results?

5. Practicality and Applicability:
- Real-world applicability: To what extent can the model be applied to real-world scenarios? 
- Practical implementation: How would this model be implemented in practice? What would be the required infrastructure, and what challenges would need to be addressed during implementation? 

Critique the analysis without offering any constructive suggestions—your focus should solely be on highlighting weaknesses, gaps, and limitations within the approach and its execution.
"""


TASK_MODELING_IMPROVEMENT_PROMPT = """\
{data_summary}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

# Task Modeling Process:
{modeling_process}

# Task Modeling Process Critique:
{modeling_process_critique}

---

Refine and improve the existing modeling process based on the critique provided. The goal is to enhance the formulation, structure, and overall effectiveness of the model while addressing the identified gaps, flaws, or limitations. Propose more appropriate assumptions, more robust mathematical techniques, or alternative modeling approaches if necessary. Focus on improving the model's relevance, accuracy, and computational feasibility while also ensuring its ability to capture the complexity of the problem in real-world contexts.

Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
{user_prompt}
Provide a new version of the modeling process that integrates these improvements directly. DO NOT mention any previous process content and deficiencies.

IMPROVED MODELING PROCESS:
"""

TASK_CODING_PROMPT = """\
# Dataset Path:
{data_file}

# Data Description:
{data_summary}

# Variable Description:
{variable_description}

# Other files (Generated by Other Agents):
{dependent_file_prompt}

# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{modeling_formulas}

# Task Modeling Process:
{modeling_process}

# Code Template:
{code_template}

---

## Role & Collaboration:
You are an expert programmer working as part of a multi-agent system. Your role is to implement the code based on the provided dataset (**refer to the Dataset Path, Dataset Description, and Variable Description**) **or preprocessed files generated by other agents** (**refer to "Other Files"**), along with the modeling process and given code template. Other agents will use your results to make decisions, but they will **not** review your code. Therefore, it is crucial that:
1. **Ensure the code is executable** and will successfully run without errors, producing the expected results. **It should be tested to verify it works in the intended environment**.
2. **Reuse files from "Other Files" whenever possible** instead of redoing tasks that have already been completed by other agents.
3. **All data processing steps must save the processed results to local files (CSV, JSON, or pickle) for easy access by other agents.**
4. **The output should be as detailed as possible**, including intermediate results and final outputs.
5. **Ensure transparency** by logging key computation steps and providing clear outputs.

## Implementation Guidelines:
- **Prioritize using files from "Other Files" before processing raw data** to avoid redundant computation.
- Follow the provided **modeling formulas** and **modeling process** precisely.
- The **code must be executable**: ensure that the Python code you generate runs without errors. Do not just focus on producing the correct output format; **focus on producing a working solution** that can be executed successfully in a Python environment.
- **Store intermediate and final data processing results to local** in appropriate formats (e.g., CSV, JSON, or pickle).
- Provide **detailed print/logging outputs** to ensure that other agents can understand the results without needing to read the code.
{user_prompt}

## Expected Response Format:
You **MUST** return the Python implementation in the following format:
```python
# Here is the Python code.
"""


TASK_CODING_DEBUG_PROMPT = """\
# Code Template:
{code_template}

# Modeling Process:
{modeling_process}

# Current Code:
{code}

However, there are some bugs in this version. Here is the execution result:
# Execution Result:
{observation}

---

You are a helpful programming expert. Based on the provided execution result, please revise the script to fix these bugs. Your task is to address the error indicated in the result, and refine or modify the code as needed to ensure it works correctly.
{user_prompt}
Please respond exactly in the following format:
```python
# Provide the corrected python code here.
```
"""


TASK_RESULT_PROMPT = """\
# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{task_formulas}

# Task Modeling:
{task_modeling}

---

Based on the task description, analysis, and modeling framework, present a comprehensive and detailed account of the intermediate results, calculations, and outcomes generated during the task. Clearly articulate the results of any simulations, experiments, or calculations, providing numerical values, data trends, or statistical measures as necessary. If visual representations such as graphs, charts, or tables were used to communicate the results, ensure they are clearly labeled and explained, highlighting their relevance to the overall task. Discuss the intermediate steps or processes that led to the results, including any transformations or assumptions made during calculations. If applicable, compare and contrast these results with expected outcomes or previously known results to gauge the task’s success. Provide a thoughtful interpretation of the findings, considering how they contribute to advancing understanding or solving the problem at hand, and highlight any areas where further investigation or refinement may be needed.
{user_prompt}
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text and LaTeX for formulas only, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""

TASK_RESULT_WITH_CODE_PROMPT = """\
# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{task_formulas}

# Task Modeling:
{task_modeling}

# Code Execution Result:
{execution_result}

---

Based on the task description, analysis, modeling framework, and code execution result, present a comprehensive and detailed account of the intermediate results, calculations, and outcomes generated during the task. Clearly articulate the results of any computations or operations performed, providing numerical values, data trends, or statistical measures as necessary. If visual representations such as graphs, charts, or tables were used to communicate the results, ensure they are clearly labeled and explained, highlighting their relevance to the overall task. Discuss the intermediate steps or processes that led to the results, including any transformations or assumptions made during calculations. If applicable, compare and contrast these results with expected outcomes or previously known results to gauge the task’s success. Provide a thoughtful interpretation of the findings, considering how they contribute to advancing understanding or solving the problem at hand, and highlight any areas where further investigation or refinement may be needed.
{user_prompt}
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text and LaTeX for formulas only, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


TASK_ANSWER_PROMPT = """\
# Task Description:
{task_description}

# Task Analysis:
{task_analysis}

# Task Modeling Formulas:
{task_formulas}

# Task Modeling:
{task_modeling}

# Task Result:
{task_result}

---

Craft a comprehensive and insightful answer section that synthesizes the findings presented in the results section to directly address the research questions and objectives outlined at the outset of the study. Begin by clearly stating the primary conclusions drawn from the analysis, ensuring that each conclusion is explicitly linked to specific aspects of the results. Discuss how these conclusions validate or challenge the initial hypotheses or theoretical expectations, providing a coherent narrative that illustrates the progression from data to insight.

Evaluate the effectiveness and reliability of the mathematical models employed, highlighting strengths such as predictive accuracy, robustness, or computational efficiency. Address any limitations encountered during the modeling process, explaining how they may impact the validity of the conclusions and suggesting potential remedies or alternative approaches. Consider the sensitivity of the model to various parameters and the extent to which the results are generalizable to other contexts or applications.

Analyze potential biases that may have influenced the results, including data bias, model bias, and computational bias. Discuss whether the dataset is representative of the problem space and whether any imbalances, selection biases, or sampling limitations might have affected the conclusions. Examine modeling assumptions, parameter choices, and architectural constraints that could introduce systematic deviations in the results. Assess how numerical precision, algorithmic approximations, or implementation details might influence the stability and fairness of the model’s predictions.

Discuss strategies to mitigate identified biases and improve the reliability of the conclusions. Consider adjustments in data preprocessing, such as resampling, normalization, or augmentation, to address distribution imbalances. Explore refinements to the modeling process, including regularization techniques, fairness constraints, and sensitivity analyses, to ensure robustness across different scenarios. Evaluate the impact of alternative modeling approaches and discuss the extent to which the proposed methods can generalize beyond the given dataset or problem context.

Explore the broader implications of the findings for the field of study, identifying how they contribute to existing knowledge, inform future research directions, or influence practical applications. Discuss any unexpected outcomes and their significance, offering interpretations that may reveal new avenues for exploration or theoretical development. Reflect on the societal, economic, or environmental relevance of the results, if applicable, and propose recommendations based on the study’s insights.

Conclude the section by summarizing the key takeaways, emphasizing the contribution of the research to solving the problem at hand, and outlining the next steps for further investigation or implementation. Ensure that the discussion is logically structured, with each paragraph building upon the previous ones to form a cohesive and persuasive argument that underscores the study’s value and impact.

The content of this Task Answer section should be distinct and not merely a repetition of the Task Result section. Ensure that there is no duplication.

{user_prompt}

Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text and LaTeX for formulas only, without any Markdown formatting or syntax. Written as one or more cohesive paragraphs. Avoid structuring your answer in bullet points or numbered lists.
"""


CREATE_CHART_PROMPT = """\
## Instruction
Create a highly detailed and comprehensive chart that effectively visualizes the complex mathematical relationships and insights presented in the provided mathematical modeling paper. Begin by selecting the most appropriate type of chart—such as a line graph, bar chart, scatter plot, heatmap, or 3D surface plot—based on the nature of the data and the specific relationships being analyzed. Clearly define the variables involved, including their units and scales, and incorporate any derived metrics that enhance interpretability. Ensure that the axes are labeled accurately and descriptively, with appropriate units and scales, whether linear or logarithmic, to best represent the data distribution and relationships. Include a clear and concise legend that distinguishes between different datasets or variables, using distinct colors or patterns that are both aesthetically pleasing and easily distinguishable. Utilize gridlines to aid in the accurate reading of values, and choose a color scheme that enhances readability while maintaining visual appeal.

Emphasize the core purpose of the chart, whether it is to highlight trends over time, compare different values, show distributions, illustrate correlations, validate theoretical models, or support key arguments within the paper. Articulate the intended message of the chart clearly, ensuring that every design choice—from the type of chart to the specific visual elements used—aligns with the objectives of the mathematical modeling paper. Incorporate multiple lines or bars if comparing different datasets, use shading or contouring for density representation, and add error bars to indicate uncertainty where applicable. Include annotations to highlight significant data points, trends, or anomalies that are critical to the analysis, providing context and explanations that guide the viewer’s understanding.

Balance aesthetics with functionality by selecting colors and contrasts that not only make the chart visually compelling but also enhance readability and comprehension. Avoid unnecessary complexity by keeping the design clean and focused, ensuring that the chart remains clear and easy to interpret without sacrificing accuracy or depth of information. If beneficial, incorporate supplementary visual aids such as trend lines, regression curves, or overlays of empirical and theoretical results to strengthen the analysis and provide additional layers of insight. The final chart should serve as a precise and compelling visualization that effectively conveys the mathematical insights, facilitates understanding, and robustly supports the overall narrative and conclusions of the mathematical modeling paper.

{user_prompt}

## Paper Content
<paper>  
{paper_content}  
</paper>  

## Existing Charts
{existing_charts}  

## Create a New Chart

Please create a chart that aligns closely with the above paper content while avoiding redundancy with existing charts. Follow the markdown format below to describe your chart:  

**Chart Title**  
[Provide a clear and descriptive title for the chart]  

**Chart Type**  
[Specify the type of chart]  

**Purpose**  
[Describe the core purpose of the chart in a paragraph]  

**Data or Variables**  
[Describe the data or variables used in the chart in a paragraph]  

**Chart Presentation Guidelines**  
[A comprehensive guide on chart presentation, covering data representation, key layout elements, units, axis labels, legends, gridlines, annotations, and other essential considerations for effective visualization.]

**Intended Message**  
[Articulate the key message or insight the chart is intended to convey in a paragraph]
"""



PROBLEM_EXTRACT_PROMPT = """\
You are tasked with extracting detailed and complete information from the following mathematical modeling question.  

<MODELING_QUESTION>
{question}
</MODELING_QUESTION>

### Extraction Requirements:  
From the provided `<MODELING_QUESTION>`, extract and organize the following information as accurately and comprehensively as possible. Preserve the original text wherever applicable and do not omit any relevant details.  

1. **"BACKGROUND"**: Extract all background information that provides context for the problem. This includes the problem’s domain, motivation, assumptions, or any other relevant introductory details.  
2. **"TASK_REQUIREMENTS"**: A String to list all the requirements that need to be solved and satisfied, including specific instructions, constraints, objectives, and expected outputs.  
3. **"DATA_FILES"**: A List to identify and list all dataset filenames mentioned in the question (if applicable). There may be multiple dataset files.  
4. **"DATA_DESCRIPTIONS"**: Extract dataset descriptions, including details about the structure, features, variables, or metadata. If dataset descriptions are provided in a separate file, extract and list the filename instead.  
5. **"ADDENDUM"**: Include any additional information that might be useful for solving the problem. This can include notes, references, clarifications, hints, or supplementary instructions.  

### Expected Response Format:  
Provide the extracted information in the following structured JSON format:  

```json
{{
  "background": "",
  "task_requirements": "",
  "data_files": [],
  "data_descriptions": "",
  "addendum": ""
}}
```

Ensure maximum fidelity to the original text and extract details as comprehensively as possible.
"""



TASK_DEPENDENCY_ANALYSIS_PROMPT = """\
Understanding the dependencies among different tasks in a mathematical modeling process is crucial for ensuring a coherent, logically structured, and efficient solution. Given a mathematical modeling problem and its solution decomposition into {tasknum} subtasks, analyze the interdependencies among these subtasks.  

## Input Information:
- **Mathematical Modeling Problem:** {modeling_problem}
- **Problem Analysis:** {problem_analysis}
- **Modeling Solution:** {modeling_solution}
- **Decomposed Tasks:** {task_descriptions}

## Task Dependency Analysis Instructions:
1. **Identify Task Dependencies:** For each task, determine which preceding tasks provide necessary input, data, or conditions for its execution. Clearly outline how earlier tasks influence or constrain later ones.
2. **Describe Dependency Types:** Specify the nature of the dependencies between tasks. This includes:
   - *Data Dependency:* When one task produces outputs that are required as inputs for another task.
   - *Methodological Dependency:* When a later task builds upon a theoretical framework, assumptions, or models established by an earlier task.
   - *Computational Dependency:* When a task requires prior computations or optimizations to be completed before proceeding.
   - *Structural Dependency:* When a task is logically required to be completed before another due to hierarchical or sequential constraints.
3. **Ensure Completeness:** Verify that all tasks in the decomposition are accounted for in the dependency analysis and that no essential dependencies are missing.

## Output Format:  
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as {tasknum} cohesive paragraphs, each paragraph is a dependency analysis of a task.

The response should be comprehensive and written in a clear, well-structured format without bullet points, ensuring a logical flow of dependency relationships and their implications.
"""


TASK_DEPENDENCY_ANALYSIS_WITH_CODE_PROMPT = """\
Understanding the dependencies among different tasks in a mathematical modeling process is crucial for ensuring a coherent, logically structured, and efficient solution. Given a mathematical modeling problem and its solution decomposition into {tasknum} subtasks, analyze the interdependencies among these subtasks.  

## Input Information:
- **Mathematical Modeling Problem:** {modeling_problem}
- **Problem Analysis:** {problem_analysis}
- **Modeling Solution:** {modeling_solution}
- **Decomposed Tasks:** {task_descriptions}

## Task Dependency Analysis Instructions:
1. **Identify Task Dependencies:** For each task, determine which preceding tasks provide necessary input, data, or conditions for its execution. Clearly outline how earlier tasks influence or constrain later ones.
2. **Describe Dependency Types:** Specify the nature of the dependencies between tasks. This includes:
   - *Data Dependency:* When one task produces outputs that are required as inputs for another task.
   - *Methodological Dependency:* When a later task builds upon a theoretical framework, assumptions, or models established by an earlier task.
   - *Computational Dependency:* When a task requires prior computations or optimizations to be completed before proceeding.
   - *Structural Dependency:* When a task is logically required to be completed before another due to hierarchical or sequential constraints.
   - *Code Dependency:* When one task relies on code structures, functions, or modules that are defined or executed in a preceding task. This includes shared variables, functions, or libraries that must be defined before their use in later tasks.
3. **Ensure Completeness:** Verify that all tasks in the decomposition are accounted for in the dependency analysis and that no essential dependencies are missing.

## Output Format:  
Respond as comprehensively and in as much detail as possible. Do not format your response in Markdown. Using plain text, without any Markdown formatting or syntax. Written as {tasknum} cohesive paragraphs, each paragraph is a dependency analysis of a task.

The response should be comprehensive and written in a clear, well-structured format without bullet points, ensuring a logical flow of dependency relationships and their implications.
"""


DAG_CONSTRUCTION_PROMPT = """\
A well-structured Directed Acyclic Graph (DAG) is essential for visualizing and optimizing the dependencies between different tasks in a mathematical modeling process. Given a problem and its solution decomposition into {tasknum} subtasks, construct a DAG that accurately represents the dependency relationships among these tasks. The DAG should capture all necessary dependencies while ensuring that no cycles exist in the structure.  

## Input Information:
- **Mathematical Modeling Problem:** {modeling_problem}
- **Problem Analysis:** {problem_analysis}
- **Modeling Solution:** {modeling_solution}
- **Decomposed Tasks:** {task_descriptions}
- **Dependency Analysis:** {task_dependency_analysis}

## Output Format (STRICT REQUIREMENT):
You **MUST** return a valid JSON-formatted adjacency list **without** any additional text, explanations, or comments. **Only** output the JSON object.

### JSON Format (Strictly Follow This Format):
```json
{{
  "task_ID": [dependent_IDs],
  ...
}}

## Example Output: 
```json
{{
"1": []
"2": ['1']
"3": ['1']
"4": ['2', '3']
}}
```
"""

# TASK_ANALYSIS_APPEND_PROMPT = """\
# When analyzing the current task, please pay careful attention to its dependencies on other tasks. Ensure that you consider how the outputs or results from preceding tasks influence the execution and outcomes of this task. Identify any tasks that provide necessary inputs, data, or models, and explain how these dependencies shape the approach, methods, and overall execution of the task at hand. This analysis should be informed by the task dependency relationships, which will help clarify how the current task fits into the broader project or workflow. Keep in mind that the successful completion of this task may depend on the timely and correct completion of other tasks, and any delays or issues in the dependent tasks could impact the current task’s progress and outcomes.
# """
#             
# TASK_FORMULAS_APPEND_PROMPT = """\
# When formulating the mathematical model for the current task, it is essential to consider how this task depends on other tasks in the overall process. Be sure to analyze how the results, data, or models produced by preceding tasks influence the formulation of the current task. Identify any critical inputs or assumptions that come from earlier tasks and explain how these shape the approach, variables, or constraints in the mathematical formulation. In particular, pay attention to how the completion of dependent tasks impacts the accuracy, feasibility, or computational aspects of the model. This dependency analysis will help ensure that the model reflects the correct sequence of steps, and that any limitations or challenges arising from earlier tasks are properly accounted for. Ensure that the interdependencies between tasks are fully integrated into the mathematical formulation to maintain consistency and validity across the entire modeling process.
# """
# 
# TASK_MODELING_APPEND_PROMPT = """\
# Please continue the modeling process by considering the dependencies between the current task and the preceding tasks. Begin by analyzing how the outputs or models from earlier tasks influence the formulation and execution of the current task. Describe the interdependencies in detail, explaining how the results from previous tasks provide necessary data, constraints, or assumptions that affect the current task's modeling approach. Identify any key variables, parameters, or methods that are directly linked to earlier tasks and discuss how their incorporation into the current task ensures consistency and accuracy across the entire modeling framework. Additionally, consider any potential challenges or limitations introduced by the dependencies, such as delays or uncertainty in the results from prior tasks, and explain how these factors might be addressed in the modeling process. Ensure that these dependencies are clearly integrated into the continued modeling effort, providing a cohesive and comprehensive understanding of how the tasks interconnect and contribute to the overall solution.
# """

TASK_ANALYSIS_APPEND_PROMPT = """\
When analyzing the current task, please pay careful attention to its dependencies on other tasks.
"""
            
TASK_FORMULAS_APPEND_PROMPT = """\
When formulating the mathematical model for the current task, it is essential to consider how this task depends on other tasks in the overall process.
"""

TASK_MODELING_APPEND_PROMPT = """\
Please consider the dependencies between the current task and the preceding tasks.
"""

CODE_STRUCTURE_PROMPT = """\
You are a programming expert. Please extract the structure from the following code and output it in the following JSON format, please return an empty list if the corresponding item is not available.:
The code is:
```python
{code}
```
The output format is:
```json
{{
    "script_path": {save_path}
    "class": [
    {{
      "name": class name,
      "description": description of class,
      "class_functions": [
        {{
          "name": function name,
          "description": description of class function,
          "parameters": [
            {{
              "name": param name,
              "type": param type,
              "description": description of param,
            }},
            ...
          ],
          "returns": {{
            "description": "return of the function."
          }},
        }}
      ]
    }}
  ],
  "function": [
    {{
      "name": function name,
      "description": description of class function,
      "parameters": [
        {{
          "name": param name,
          "type": param type,
          "description": description of param,
        }},
        ...
      ],
      "returns": {{
        "description": "return of the function."
      }},
    }}
  ],
  "file_outputs": [
    {{
      "path": "file_path",
      "file_description": "description of the file",
      "column_name": ["column_name_if_csv_else_None"]
    }},
    ...
  ]
}}
```
"""


PAPER_CHAPTER_PROMPT = """\
You are tasked with creating a publication-quality LaTeX chapter for a mathematical modeling research paper. Carefully transform the provided structured draft into a coherent, rigorous, and concise narrative chapter that aligns logically and seamlessly with the previously written content.

## Target Chapter:
{chapter_path}

## Structured Draft:
<structured_draft>
{json_context}
</structured_draft>

## Preceding Chapters (for seamless narrative integration and avoiding repetition):
<preceding_content>
{previous_chapters}
</preceding_content>


## Requirements:
- Write exclusively in accurate, idiomatic LaTeX; avoid Markdown syntax and symbols entirely.
- Clearly indicate the chapter content corresponds precisely to the target chapter `{chapter_path}`; do not repeat or reference explicitly the content of other chapters.
- Integrate any mathematical formulas properly using correct LaTeX environments (`\\begin{{align}}`). Truncate and wrap long formulas and symbols.
- Present the chapter as a continuous, fluent narrative without section headings, subsections, bullet points, or numbered lists, Response only chapter content, do not include headlines and anything else.
- Critically evaluate the structured draft, selecting only most high-quality important and relevant content. Remove all redundancy, eliminate low-value statements, and distill essential information clearly and succinctly.
- Maintain rigorous academic style, logical coherence, and clarity throughout, ensuring that the chapter integrates naturally with preceding chapters.

## Output Format:
```latex
CHAPTER_CONTENT_TEXT
```

"""

PAPER_CHAPTER_WITH_PRECEDING_PROMPT = """\
You are tasked with generating a publication-quality LaTeX chapter for a mathematical modeling paper. Write a cohesive, academically rigorous chapter that integrates seamlessly with the preceding content of the paper.

## Chapter to write: 
{chapter_path}

## Preceding Content: 
<preceding_content>
{previous_chapters}
</preceding_content>

## Writing Requirements:
- Use accurate and proper LaTeX syntax throughout, avoid all Markdown syntax or symbols.
- Present the content as a continuous, coherent narrative without using sections, subsections, or bullet points. Response only chapter content, do not include headlines and anything else.
- Make it clear that the section you need to write is `{chapter_path}`. Do not involve the content of other chapters.
"""

PAPER_NOTATION_PROMPT = """
You are an AI assistant trained to extract and typeset the Notations table from a mathematical modeling paper in LaTeX format. Your task is to take the input paper and output a properly formatted LaTeX table displaying the notations used in the paper. 

1. Well-structured and easy to read.
2. Properly typeset for LaTeX documents.
3. Adaptive in size and position to fit neatly into any document.
4. Truncate and wrap long formulas, symbols and text in the table for better readability.

<paper>
{previous_chapters}
</paper>

Exmple of Table Format:
```latex
\\begin{{table}}[H]
    \\centering
    \\renewcommand{{\\arraystretch}}{{1.3}}
    \\begin{{tabular}}{{>{{\\raggedright\\arraybackslash}}p{{3cm}}>{{\\raggedright\\arraybackslash}}p{{11cm}}}}
        \\toprule
        \\textbf{{Notation}} & \\textbf{{Description}} \\\\
        \\midrule
        \\( f(x) \\) & description... \\\\
        \\bottomrule
    \\end{{tabular}}
    \\caption{{Table of Notations}}
    \\label{{tab:notations}}
\\end{{table}}
```

Response only latex table content, do not include headlines and anything else.
"""


PAPER_INFO_PROMPT = """\
You are an expert academic writer tasked with analyzing paper chapters and generating key metadata for a mathematical modeling paper.

# Input Chapters
{paper_chapters}

Based on the content of these chapters, please generate:
1. A concise, descriptive title that reflects the paper's main focus
2. A comprehensive and detailed summary highlighting key findings and methodology
3. 4-6 relevant keywords that capture the paper's main themes

Returns the Legal JSON Format:
```Json
{{
    "title": "A clear, concise title",
    "summary": "A well-structured summary covering the following information: \n- Restatement and Clarification of the Problem: Describe the problem to be solved in your own words.\n- Explanation of Assumptions and Their Rationality: Highlight the assumptions made in the modeling process and clearly list all the variables required for the model.\n- Model Design and Rationality Argumentation: Specify the type of model used or describe the construction of a new model, explain how it was established and the rationale behind its design.\n- Description of Model Testing and Sensitivity Analysis: Include error analysis and other testing items.",
    "keywords": "keyword1; keyword2; keyword3; keyword4..."
}}
```

Requirements:
- Title should be specific and academic in tone
- Summary should follow standard academic abstract structure and be approximately 400 words
- Keywords should be ordered from general to specific
- must return a strictly legal JSON
"""