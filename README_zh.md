# 🤖 MM-Agent：面向真实世界数学建模问题的智能体

> 📖 当前为中文版本。 [Click here for English version](./README.md)

## 📖 简介

我们提出了一个**数学建模智能体（Mathematical Modeling Agent，简称 MM-Agent）**，模拟人类在解决真实世界数学建模问题时的完整工作流程。该智能体遵循以下四个步骤：

1. **问题分析**
2. **数学建模**
3. **计算求解**
4. **结果汇报**

我们的论文已在 [arXiv](https://arxiv.org/abs/2505.14148) 发布。

---

## 🔬 数学建模智能体如何工作？

该智能体通过以下结构化流程，模拟人类的建模过程：

1. **🧠 问题分析**
   理解问题背景、目标、可用数据以及约束条件。

2. **📐 数学建模**
   将真实问题转化为数学模型，包括设定假设、建立公式、选择建模技术等。

3. **🧮 计算求解**
   编写算法或数值方法，通过仿真或优化等手段求解模型。

4. **📝 结果汇报**
   总结建模流程，分析结果，生成结构清晰的报告。

我们提出的 MM-Agent 是一个面向开放性真实建模问题的端到端解决方案。它借鉴专家的建模工作流程，系统性地分析非结构化问题描述、构建结构化数学模型、进行求解并生成分析报告。

在所有环节中，建模阶段最具挑战性，需要将复杂的现实情境抽象为具有可行解的数学形式。为此，我们设计了分层建模知识库 **HMML（Hierarchical Mathematical Modeling Library）**，其结构涵盖领域（domain）、子领域（subdomain）、方法节点（method node）三层，共编码了 98 种高层建模方案。

HMML 支持基于问题内容和解法目标的双向检索，帮助智能体完成建模抽象与方法选择。具体来说，MM-Agent 首先分析并分解问题为多个子任务，随后通过 HMML 检索合适的方法，并结合 actor-critic 机制不断优化建模方案。在求解阶段，智能体调用 **MLE-Solver** 自动生成并迭代优化代码，以高效准确地完成求解。最终，它会生成一份结构化报告，总结建模流程、实验结果与核心洞察。

---

## 🌐 在线演示

演示地址：[Hugging Face Spaces](https://huggingface.co/spaces/MathematicalModelingAgent/MathematicalModelingAgent)

---

## 👾 当前支持的模型

* **OpenAI**：`gpt-4o`
* **DeepSeek**：`deepseek-R1`

---

## ▶️ 快速开始

### 🔧 运行智能体

你可以通过以下命令直接运行智能体：

```bash
python MMAgent/main.py --key "your_openai_key" --task "task_id"
```

**示例：**

```bash
python MMAgent/main.py --key "sk-XXX" --task "2024_C"
```

其中，`task` 参数对应 MM-Bench 中的问题编号（如 `"2024_C"` 表示 2024 年 MCM 的 C 题）。

---

## 🖥️ 安装指南

### ✅ 环境要求

* 推荐使用 Python 3.10
* 建议安装 Conda

### 💻 安装步骤

1. **克隆项目仓库**

```bash
git clone git@github.com:usail-hkust/LLM-MM-Agent.git
```

2. **创建并激活 Conda 环境**

```bash
conda create --name math_modeling python=3.10
conda activate math_modeling
```

3. **进入项目目录**

```bash
cd MM-Agent
```

4. **安装依赖项**

```bash
pip install -r requirements.txt
```

---

## 📜 许可协议

源代码遵循 **\[CC BY-NC]** 许可协议。

---

## 📚 参考文献

```bash
@misc{mmagent,  
   title={MM-Agent: LLM as Agents for Real-world Mathematical Modeling Problem},  
   author={Fan Liu and Zherui Yang and Cancheng Liu and Tianrui Song and Xiaofeng Gao and Hao Liu},  
   year={2025},  
   eprint={2505.14148},  
   archivePrefix={arXiv},  
   primaryClass={cs.AI},  
   url={https://arxiv.org/abs/2505.14148}  
}
```