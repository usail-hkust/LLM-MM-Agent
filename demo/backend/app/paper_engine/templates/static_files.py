"""
Static resources for the Paper Engine.
"""

# 1. Fast Build Script (Used ONLY for 'Run' button)
# Keeps basic integrity check to ensure fast-compile also respects structure.
BUILD_SCRIPT = r"""
import subprocess
import sys
import os
import json
import re

def check_integrity():
    if not os.path.exists("structure.json"): return True
    try:
        with open("structure.json", 'r') as f: required = json.load(f)
    except: return True

    if not os.path.exists("main.tex"): return False

    with open("main.tex", 'r') as f: content = f.read()
    clean = re.sub(r'(?<!\\)%.*', '', content)

    missing = [p for p in required if f"\\input{{{p}}}" not in clean]
    if missing:
        print(f"[INTEGRITY FAIL] Missing sections: {missing}")
        return False
    return True

def run():
    print(">>> [Fast Compile] Starting...")

    # Clean aux
    subprocess.run("rm -f *.aux *.log *.out *.pdf", shell=True)

    # Compile
    cmd = ["latexmk", "-pdf", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
    res = subprocess.run(cmd, capture_output=True, text=True)

    print(res.stdout)
    if res.stderr: print(res.stderr)

    if res.returncode != 0:
        print("\n[ERROR] Compilation Failed.")
        sys.exit(1)

    if not check_integrity():
        print("\n[ERROR] Integrity Check Failed: Content missing from main.tex.")
        sys.exit(1)

    print("\n[SUCCESS] PDF Generated.")

if __name__ == "__main__":
    run()
"""

# ... (EASYMCM_STY and MAIN_TEX_TEMPLATE remain unchanged) ...
EASYMCM_STY = r"""\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{easymcm}
\RequirePackage[a4paper,margin=1in]{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{graphicx}
\RequirePackage{amsmath}
\RequirePackage{booktabs}
\RequirePackage{hyperref}
\RequirePackage{xcolor}
\RequirePackage{float}
\pagestyle{fancy}
\lhead{Team \# \MCM@control}
\rhead{Problem \MCM@problem}
\newcommand{\MCM@control}{0000000}
\newcommand{\MCM@problem}{A}
\DeclareOption*{\edef\MCM@control{\CurrentOption}}
\ProcessOptions
\newcommand{\problem}[1]{\gdef\MCM@problem{#1}}
\newcommand{\makesheet}{
  \begin{center}
  \huge \textbf{Summary Sheet} \\
  \vspace{0.5cm}
  \large Team: \MCM@control \quad Problem: \MCM@problem
  \end{center}
  \vspace{1cm}
}
\endinput"""

MAIN_TEX_TEMPLATE = r"""\documentclass[12pt]{article}
\usepackage[{{CONTROL_NUMBER}}]{easymcm}
\problem{{{PROBLEM_ID}}}
\usepackage{times}
\usepackage{subcaption}
\usepackage{listings}
\title{{{TITLE}}}
\date{\today}
\begin{document}
\makesheet
{{ABSTRACT_INPUT}}
\tableofcontents
\newpage
{{INPUTS}}
\end{document}"""
