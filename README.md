# 🤖 MM Agent: LLMs as Agents for Real-world Mathematical Modeling Problems

> 📖 This is the English version of the README. [点击查看中文版](./README_zh.md)

## 📰 News
1. **2025-12**
   🔥 **Upcoming Update**: We will soon release the latest upgraded version of the demo (bilingual). Please **Star** 🌟 our repository! We will issue service accounts based on the Star list (due to limited server capacity).
   (即将更新：我们将很快发布最新升级版演示（双语）。请 **Star** 🌟 我们的仓库！由于服务器容量有限，我们将根据 Star 列表发放服务账号。)
2. **2025-10**
   🚀 **MM-Agent assisted two undergraduate teams in winning the Finalist Award** (Top 2.0% among 27,456 teams) in **MCM/ICM 2025**, demonstrating its practical effectiveness as a *modeling copilot*.
   🔗  [Demo](https://huggingface.co/spaces/MathematicalModelingAgent/MathematicalModelingAgent)
3. **2025-09**
   🎉 Our paper *"MM-Agent: LLMs as Agents for Real-world Mathematical Modeling Problems"* has been accepted to the **NeurIPS 2025**!
   📄 [Read the paper on arXiv](https://arxiv.org/abs/2505.14148)
4. **2025-07**
   🎉 Our paper *"MM-Agent: LLMs as Agents for Real-world Mathematical Modeling Problems"* has been accepted to the **AI4MATH Workshop at ICML 2025**!
   📄 [Read the paper on arXiv](https://arxiv.org/abs/2505.14148)

## 📖 Overview

We propose a **Mathematical Modeling Agent** that simulates the real-world human process of mathematical modeling. This agent follows a complete problem-solving pipeline:

1. **Problem Analysis**
2. **Mathematical Modeling**
3. **Computational Solving**
4. **Solution Reporting**

Our paper is available at [arXiv](https://arxiv.org/abs/2505.14148).

## 🎥 Demo Video

[**▶️ Watch the Demo Video**](assets/demo.mp4)

> 💡 Note: Click the link above to watch the demo on GitHub.

## 🖼️ Framework Overview

<div align="center">
   <img src="figs/Overview.pdf" alt="MM Agent Framework Overview" width="700px"/>
</div>



---

## 🔬 How Does the Mathematical Modeling Agent Work?

The agent simulates a real-world mathematical modeling workflow through the following structured stages:

1. **🧠 Problem Analysis**
   Understands the background, objectives, data availability, and constraints of the problem.

2. **📐 Mathematical Modeling**
   Translates real-world problems into mathematical models using appropriate assumptions, formulations, and modeling techniques.

3. **🧮 Computational Solving**
   Implements algorithms, simulations, or optimization techniques to solve the models, often involving numerical computation.

4. **📝 Solution Reporting**
   Summarizes the full modeling process, interprets results, and generates a clear, structured report.

We propose MM-Agent, an end-to-end solution for open-ended real-world modeling problems. Inspired by expert workflows, MM-Agent systematically analyzes unstructured problem descriptions, formulates structured mathematical models, derives solutions, and generates analytical reports.
Among these stages, the modeling step poses the greatest challenge, as it requires abstracting complex scenarios into mathematically coherent formulations grounded in both problem context and solution feasibility. To address this, we introduce the Hierarchical Mathematical Modeling Library (HMML): a tri-level knowledge hierarchy encompassing domains, subdomains, and method nodes. HMML encodes 98 high-level modeling schemas that enable both problem-aware and solution-aware retrieval of modeling strategies, supporting abstraction and method selection.  Specifically, MM-Agent first analyzes the problem and decomposes it into subtasks. It then retrieves suitable methods from HMML and refines its modeling plans via an actor-critic mechanism. To solve the models, the agent autonomously generates and iteratively improves code using the MLE-Solver for efficient, accurate execution. Finally, it compiles a structured report summarizing the modeling approach, experimental results, and key insights.

---
## 🌐 Demo
Our demo is available at [Hugging Face Spaces](https://huggingface.co/spaces/MathematicalModelingAgent/MathematicalModelingAgent).

---

## 👾 Currently Supported Models

* **OpenAI**: `gpt-4o`
* **DeepSeek**: `deepseek-R1`

---

## ▶️ Quick Start

### 🔧 Running the Agent

You can directly run the Mathematical Modeling Agent with:

```bash
python MMAgent/main.py --key "your_openai_key" --task "task_id"
```

**Example**:

```bash
python MMAgent/main.py --key "sk-XXX" --task "2024_C"
```

Here, `task` corresponds to the problem ID from MM-Bench (e.g., `"2024_C"` refers to the 2024 MCM problem C).

---

## 🖥️ Installation Guide

### ✅ Prerequisites

* Python 3.10 recommended
* Conda (optional but preferred)

### 💻 Setup Steps

1. **Clone the Repository**

```bash
git clone git@github.com:usail-hkust/LLM-MM-Agent.git
```

2. **Create and Activate the Conda Environment**

```bash
conda create --name math_modeling python=3.10
conda activate math_modeling
```

3. **Navigate to Project Directory**

```bash
cd MM-Agent
```

4. **Install Dependencies**

```bash
pip install -r requirements.txt
```

---

## 📜 License

Source code is licensed under the **\[CC BY-NC]**.


## 📚 References

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