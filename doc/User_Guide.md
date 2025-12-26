# User Guide / 用户指南

Welcome to the MM-Agent User Guide. This document provides detailed instructions on installation, usage, and the core workflow of the Mathematical Modeling Agent.

欢迎阅读 MM-Agent 用户指南。本文档提供了关于数学建模智能体的安装、使用及核心工作流程的详细说明。

---

## 1. Installation / 安装

### Prerequisites / 前置要求
- **Python**: 3.10 recommended / 推荐版本 3.10
- **Conda**: Recommended for environment management / 推荐用于环境管理

### Steps / 步骤

1.  **Clone the Repository / 克隆仓库**
    ```bash
    git clone git@github.com:usail-hkust/LLM-MM-Agent.git
    cd LLM-MM-Agent
    ```

2.  **Create Environment / 创建环境**
    ```bash
    conda create --name math_modeling python=3.10
    conda activate math_modeling
    ```

3.  **Install Dependencies / 安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

---

## 2. Quick Start (CLI) / 快速开始 (命令行)

You can run the agent directly from the command line to solve specific tasks from the MM-Bench dataset.
您可以直接从命令行运行智能体，以解决 MM-Bench 数据集中的特定任务。

### Command Structure / 命令结构
```bash
python MMAgent/main.py --key "YOUR_API_KEY" --task "TASK_ID"
```

### Parameters / 参数说明
- `--key`: Your LLM API Key (e.g., OpenAI API Key). / 您的 LLM API 密钥（例如 OpenAI API Key）。
- `--task`: The ID of the problem to solve (e.g., `2024_C` for 2024 MCM Problem C). / 待解决问题的 ID（例如 `2024_C` 代表 2024 年 MCM C 题）。

### Example / 示例
```bash
python MMAgent/main.py --key "sk-abcdef123456..." --task "2024_C"
```

---

## 3. Core Workflow / 核心工作流程

The MM-Agent simulates a complete human modeling process. Below is a walkthrough of the key stages.
MM-Agent 模拟了完整的人类建模过程。以下是关键阶段的演示。

### Step 1: Project Creation / 项目创建
Initialize the workspace. The agent sets up the necessary file structures and context.
初始化工作区。智能体设置必要的文件结构和上下文。
<img src="../assets/step1_project_creation.png" width="80%">

### Step 2: Upload Problem & Data / 上传问题与数据
Input the problem description and upload relevant datasets (CSV, Excel, etc.).
输入问题描述并上传相关数据集（CSV、Excel 等）。
<img src="../assets/step2_upload_data.png" width="80%">

### Step 3: Automated Modeling / 自动建模
The agent analyzes the problem, searches the HMML (Hierarchical Mathematical Modeling Library), and formulates mathematical models.
智能体分析问题，搜索 HMML（分层数学建模库），并构建数学模型。
<img src="../assets/step3_modeling.png" width="80%">

### Step 4: Data Analysis / 数据分析
The agent generates and executes code (Python) to perform data analysis, visualization, and solving.
智能体生成并执行代码（Python）以进行数据分析、可视化和求解。
<img src="../assets/step4_analysis.png" width="80%">

### Step 5: Paper Writing / 论文撰写
Based on the results, the agent generates a structured academic report or paper.
基于结果，智能体生成结构化的学术报告或论文。
<img src="../assets/step5_paper_writing.png" width="80%">

### Step 6: Project Management / 项目管理
View and manage history, logs, and exported files.
查看和管理历史记录、日志及导出文件。
<img src="../assets/step6_project_management.png" width="80%">

---

## 4. Configuration / 配置

### Supported Models / 支持的模型
- **OpenAI**: `gpt-4o`
- **DeepSeek**: `deepseek-R1`

To change the model or other settings, you may need to modify `config.yaml` or arguments in the script (depending on specific version updates).
如需更改模型或其他设置，可能需要修改 `config.yaml` 或脚本中的参数（视具体版本更新而定）。

---

## 5. Troubleshooting / 常见问题排查

- **API Errors**: Ensure your API key is valid and has sufficient quota. / **API 错误**：确保您的 API 密钥有效且额度充足。
- **Dependency Issues**: Try reinstalling requirements (`pip install -r requirements.txt`). / **依赖问题**：尝试重新安装依赖项。
- **Output Files**: Results are typically saved in the `output` or specific task directories. / **输出文件**：结果通常保存在 `output` 或特定任务目录中。
