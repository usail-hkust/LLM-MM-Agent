modeling_methods = """\
## Operations Research

### Programming Theory
#### Linear Programming
- Linear Programming (LP)
- Integer Programming (IP)
- Mixed Integer Programming (MIP)
- Goal Programming (GP)
- Multi-Objective Programming (MOP)
- Multi-level Programming
- Dynamic Programming (DP)
- Network Optimization Models
- Parametric Linear Programming

#### Nonlinear Programming
- Convex Programming
- Quadratic Programming (QP)
- Nonlinear Programming (NLP)
- Semi-Definite Programming (SDP)
- Set Programming
- Non-Smooth Optimization
- Penalty Methods in Nonlinear Optimization

#### Others
- Fuzzy Optimization
- Stochastic Optimization
- Robust Optimization
- Approximation Algorithms
- Cooperative Game Theory
- Metaheuristic Approaches (Simulated Annealing, Genetic Algorithms, etc.)

### Graph Theory
#### Path
- Shortest Path Model (S-T, All-Pairs)
- Dijkstra’s Algorithm
- A* Algorithm
- Bellman-Ford Algorithm
- Eulerian Path Problem
- Hamiltonian Cycle Problem
- Traveling Salesman Problem (TSP)
- Vehicle Routing Problem (VRP)
- K-Shortest Path Problem
- Path Planning Algorithms

#### Tree
- Minimum Spanning Tree (MST)
- Prim’s Algorithm
- Kruskal’s Algorithm
- Huffman Tree
- Steiner Tree Problem
- Binary Search Tree (BST)
- AVL Tree
- K-d Tree
- Quad Tree
- B+ Tree

#### Flow
- Max-Flow Min-Cost Max-Flow Problem
- Ford-Fulkerson Algorithm
- Edmonds-Karp Algorithm
- Minimum-Cost Flow Problem
- Multi-Commodity Flow Problem
- Network Reliability Models

#### Others
- Bipartite Matching Model
- Stable Marriage Problem
- Graph Coloring Problem (Greedy Coloring, Backtracking)
- Vertex Cover Problem
- Set Cover Problem
- Clique Problem
- Independent Set Problem
- Algebraic Representation of Graph (Adjacency Matrix, Laplacian Matrix, Incidence Matrix)
- Spectral Graph Theory Models

### Stochastic Programming Theory
- Stochastic Linear Programming
- Markov Chains and Models
- Markov Decision Process (MDP)
- Queuing Theory (M/M/1, M/G/1, G/G/1 Queues)
- Inventory Theory (Economic Order Quantity, Newsvendor Problem)
- Monte Carlo Simulation
- Reliability Theory
- Decision Trees and Multi-Stage Decision Problems
- Dynamic Stochastic Optimization

## Optimization Methods

### Deterministic Algorithms
- Greedy Algorithm
- Divide & Conquer
- Dynamic Programming
- Backtracking Algorithms
- Local Search Algorithms
- Branch and Bound

### Heuristic Algorithms
- Simulated Annealing (SA)
- Tabu Search
- Genetic Algorithm (GA)
- Particle Swarm Optimization (PSO)
- Ant Colony Optimization (ACO)
- Harmony Search Algorithm
- Differential Evolution
- Memetic Algorithm
- Iterative Deepening Search

### Iterative Algorithms
- Gradient Descent
- Newton's Method
- Coordinate Descent
- Conjugate Gradient Method
- Broyden–Fletcher–Goldfarb–Shanno (BFGS) Method
- Levenberg-Marquardt Algorithm
- Golden-Section Search
- Nelder-Mead Simplex Algorithm

### Constrained Optimization
- Linear Programming (LP) Solvers (Simplex Method, Interior-Point Method)
- Quadratic Programming (QP) Solvers
- Feasible Direction Method
- Projected Gradient Method
- Augmented Lagrangian Methods
- Lagrange Multipliers
- Karush-Kuhn-Tucker Conditions
- KKT Conditions in Nonlinear Optimization
- Primal-Dual Methods

### Solution Techniques
- Branch and Bound Method
- Relaxation Methods
- Penalty Function Methods
- Restriction Method
- Lagrange Relaxation
- Antithesis Optimization
- Subgradient Methods
- Multigrid Methods

---

## Machine Learning Topics

### Classification
- K-Nearest Neighbors (KNN)
- Support Vector Machine (SVM)
- Decision Trees
- Random Forest
- Gradient Boosting Machines (GBM)
- XGBoost, LightGBM, CatBoost
- Logistic Regression
- Naive Bayes
- Linear Discriminant Analysis (LDA)
- Quadratic Discriminant Analysis (QDA)
- Neural Networks (Feedforward, Convolutional, Recurrent)
- Deep Learning (CNN, RNN, LSTM)

### Clustering
- K-Means Algorithm
- K-Means++ Variant
- Expectation-Maximization (EM)
- Self-Organizing Maps (SOM)
- DBSCAN (Density-Based Spatial Clustering)
- Hierarchical Clustering
- Agglomerative and Divisive Clustering
- Spectral Clustering
- Gaussian Mixture Models (GMM)
- Affinity Propagation
- Birch Clustering

### Regression
- Linear Regression
- Ridge Regression
- Lasso Regression
- Elastic Net Regression
- Poisson Regression
- Logistic Regression (for binary classification)
- Polynomial Regression
- Generalized Linear Models (GLM)
- Non-Linear Regression
- Locally Weighted Regression (Loess)

### Dimensionality Reduction
#### Linear
- Principal Component Analysis (PCA)
- Canonical Correlation Analysis (CCA)
- Independent Component Analysis (ICA)
- Singular Value Decomposition (SVD)

#### Non-Linear
- Local Linear Embedding (LLE)
- Laplacian Eigenmaps
- t-Distributed Stochastic Neighbor Embedding (t-SNE)
- Isomap
- Autoencoders

### Ensemble Learning Algorithms
- Bagging Algorithm
- Boosting Algorithm
- Random Forest
- AdaBoost
- Gradient Boosting
- Stacking
- Voting Classifier
- Bootstrap Aggregating

## Prediction Topics

### Discrete Prediction
- Markov Decision Process (MDP)
- Hidden Markov Models (HMM)
- Grey Forecasting
- Bayesian Networks
- Difference Equations
- Kalman Filtering
- Particle Filtering

### Continuous Prediction
#### Time Series Models
- Autoregressive Integrated Moving Average (ARIMA)
- Generalized Autoregressive Conditional Heteroskedasticity (GARCH)
- Exponential Smoothing (Holt-Winters)
- Seasonal Decomposition of Time Series (STL)
- Prophet Model

#### Differential Equation Models
- Ordinary Differential Equations (ODE)
- Stochastic Differential Equations (SDE)
- Infectious Disease Models (SIR, SEIR)
- Population Growth Models
- Lotka-Volterra Models
- Heat Conduction Models
- Predator-Prey Models
- Diffusion Models (e.g., River Pollutant Diffusion)
- Economic Growth Models
- Battle Models (e.g., Lotka-Volterra Models)

## Evaluation Topics

### Scoring Evaluation
- Fuzzy Comprehensive Evaluation
- Grey Evaluation Method
- Analytic Hierarchy Process (AHP)
- Analytic Network Process (ANP)
- Data Envelopment Analysis (DEA)
- Technique for Order Preference by Similarity to Ideal Solution (TOPSIS)
- Entropy Weight Method
- Information Entropy Method
- Weighted Sum Method
- Weighted Product Method
- Multi-Criteria Decision Analysis (MCDA)
- PROMETHEE and GAIA

### Statistical Evaluation
#### Correlation Test
- Pearson Correlation Coefficient
- Spearman's Rank Correlation Coefficient
- Kendall’s Tau Coefficient
- Wilcoxon's Signed Rank Test
- Kruskal-Wallis Test
- Mann-Whitney U Test

#### Goodness of Fit Test
- Analysis of Variance (ANOVA)
- Chi-Square Goodness-of-Fit Test
- Kolmogorov-Smirnov Test (KS Test)
- Anderson-Darling Test
- Shapiro-Wilk Test
- Jarque-Bera Test
- Bayesian Information Criterion (BIC)
"""