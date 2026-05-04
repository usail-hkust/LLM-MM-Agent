"""
Blueprint Registry - Static Topology.

Singleton registry to look up node definitions and calculate dependencies.
[Updated] Added dynamic phase indexing and linear pipeline helpers (get_phase_index, get_global_index, is_driver, get_dependents).
[FIX] Enabled 'can_edit_content' for all GENERATOR nodes to support manual refinement.
"""
from typing import List, Optional, Dict
from app.domain.blueprints import NodeBlueprint, UXConfig, IterationStrategy, InteractionPolicy, OutputSpec
from app.core.definitions import NodeType, RenderType, LayoutMode

# --- Mock Static Definition (In prod, could load from YAML) ---
_DEFAULTS = [
    # Phase 1: Analysis
    NodeBlueprint(
        id="1.1", 
        title="Problem Analysis", 
        phase_label="Phase 1: Analysis",
        node_type=NodeType.GENERATOR, 
        templates={"generate": "base/standard_user.j2"},
        # [FIX] Enable Editing
        interaction=InteractionPolicy(can_edit_content=True, can_reexecute=True),
        ux=UXConfig(primary_view=RenderType.MARKDOWN_VIEWER)
    ),
    # [MODIFIED] Node 1.2: Deep Data Exploration & Reporting
    NodeBlueprint(
        id="1.2",
        title="Data Exploration",  # [Changed] Reflected wider scope
        phase_label="Phase 1: Analysis",
        node_type=NodeType.EXECUTOR,
        interaction=InteractionPolicy(can_reexecute=True, can_edit_content=True),
        ux=UXConfig(
            primary_view=RenderType.CODE_EDITOR,
            show_console=True,
            show_artifacts=True, # [Changed] Ensure report is visible
            layout_mode=LayoutMode.WORKBENCH
        ),
        meta={
            "executor_engine": "agentic_claude",
            "language": "python",
            "agent_role": "Senior Data Scientist", # [Changed]
            "agent_focus": "exploratory_analysis", # [Changed]
            
            # [Changed] Comprehensive Directive ensuring Code Execution + Report Generation
            "primary_directive": (
                "Execute a comprehensive **Forensic Data Audit** to establish the empirical validity of the modeling process. "
                "1. **Data Integrity & Topology**: Implement robust ingestion pipelines to sanitize input streams, resolving encoding anomalies and structural inconsistencies immediately. "
                "2. **Statistical Phenomenology**: Conduct a deep-dive analysis of feature-space topology, examining distributional properties (skewness, kurtosis), covariance structures, and stochastic anomalies. "
                "**STRICT CONSTRAINT**: This process is **Time-Boxed**. Prioritize the identification of critical modeling impediments (e.g., sparsity, multicollinearity) over exhaustive enumeration. "
                "3. **Strategic Reporting**: Synthesize findings into `data_exploration_report.md`. "
                "This report MUST articulate the **physical and mathematical implications** of the data structure on downstream model selection, ensuring all assumptions are data-driven. "
                "4. **Visual Evidence with Maximum Diversity**: Generate diverse plots to support the audit. **CRITICAL REQUIREMENT**: Ensure **Maximum Diversity** of visualizations. **Every plot type MUST be different** (e.g., Histogram, Scatter Plot, Boxplot, Heatmap, Contour Plot, Violin Plot, 3D Surface, Chord Diagram, ...). **DO NOT repeat any chart type**. If you generate multiple plots, each one must use a distinct visualization technique."
            )
        }
    ),
    # Node 1.3: Subtask Planning (Generator)
    NodeBlueprint(
        id="1.3", 
        title="Subtask Planning", 
        phase_label="Phase 1: Analysis",
        node_type=NodeType.GENERATOR, 
        templates={"generate": "nodes/1.3/generator.j2"}, 
        is_structural=True,
        # [FIX] Enable Editing along with Selection
        interaction=InteractionPolicy(can_select_alternatives=True, can_reexecute=True, can_edit_content=True),
        ux=UXConfig(primary_view=RenderType.SCA_PLAN_CARD, layout_mode=LayoutMode.SELECTION),
        output_spec=OutputSpec(expected_type="json", target_label="sub_problem_list")
    ),
    
    # Phase 2: Modeling
    # Node 2.1: Model Design (Generator)
    NodeBlueprint(
        id="2.1", 
        title="Model Design", 
        phase_label="Phase 2: Modeling",
        node_type=NodeType.GENERATOR, 
        templates={"generate": "nodes/2.1/generator.j2"},
        iteration=IterationStrategy(
            driver_node_id="1.3",
            driver_output_tag="sub_problem_list", 
            context_slice_key="current_sub_task" 
        ),
        # [FIX] Enable Editing
        interaction=InteractionPolicy(can_edit_content=True, can_reexecute=True),
        ux=UXConfig(layout_mode=LayoutMode.WORKBENCH)
    ),
    # Node 2.2: Code Implementation
    NodeBlueprint(
        id="2.2", 
        title="Code Implementation", 
        phase_label="Phase 2: Modeling",
        node_type=NodeType.EXECUTOR, 
        # [UPDATED DEPENDENCY] Depends on 1.3 now (was 1.2)
        iteration=IterationStrategy(
            driver_node_id="1.3",
            driver_output_tag="sub_problem_list",
            context_slice_key="current_sub_task"
        ),
        interaction=InteractionPolicy(can_reexecute=True, can_edit_content=True),
        ux=UXConfig(
            primary_view=RenderType.CODE_EDITOR, 
            show_console=True, 
            show_artifacts=True,
            layout_mode=LayoutMode.WORKBENCH
        ),
        meta={
            "executor_engine": "agentic_claude",
            "language": "python",
            "agent_role": "Machine Learning Engineer",
            "agent_focus": "implementation",
            "primary_directive": (
                "Translate the abstract mathematical formalism into a **High-Fidelity Computational Kernel**. "
                "**CORE FOCUS**: This node is **EXCLUSIVELY** for modeling and code implementation. **DO NOT** generate any visualizations, plots, charts, or images. "
                "1. **Numerical Implementation**: Construct a Python-based solver/simulation strictly adhering to the defined mathematical specifications. Prioritize numerical stability and algorithmic efficiency. "
                "2. **Result Serialization**: Persist solution vectors, state matrices, and simulation logs to structured CSV/JSON formats for downstream analysis. "
                "**STRICT CONSTRAINT**: **Zero-Exploration Policy**. Do not attempt to reinvent the model or engage in open-ended optimization. Implement the defined logic with production-level reliability and terminate immediately to conserve resources. "
                "**VISUALIZATION BAN**: **ABSOLUTELY NO PLOTS OR CHARTS**. This step focuses purely on code implementation, calculation, and data serialization. Visualization will be handled separately in the next step (Node 2.3)."
            )
        }
    ),
    # [NEW] Node 2.3: Visualization
    # Added after 2.2 to separate calculation from plotting
    NodeBlueprint(
        id="2.3",
        title="Visualization",
        phase_label="Phase 2: Modeling",
        node_type=NodeType.EXECUTOR,
        iteration=IterationStrategy(
            driver_node_id="1.3",
            driver_output_tag="sub_problem_list",
            context_slice_key="current_sub_task"
        ),
        interaction=InteractionPolicy(can_reexecute=True, can_edit_content=True),
        ux=UXConfig(
            primary_view=RenderType.ARTIFACT_GALLERY, # Focus on images
            show_console=True,
            show_artifacts=True,
            layout_mode=LayoutMode.WORKBENCH
        ),
        meta={
            "executor_engine": "agentic_claude",
            "language": "python",
            "agent_role": "Data Visualization Specialist",
            "agent_focus": "visualization",
            "primary_directive": (
                "**Visual Evidence Construction**. **DIRECTIVE**: Transform numerical artifacts into publication-quality proofs. "
                "**CORE FOCUS**: This node is **EXCLUSIVELY** for visualization. Generate diverse, high-quality plots to support the analysis. "
                "1. **Maximum Visual Diversity - CRITICAL**: Enforce a **Strict Non-Repetition Protocol** for chart types. **Every plot type MUST be different**. "
                "   - If a scatter plot is used, the next must be a heatmap, contour plot, violin plot, 3D surface, chord diagram, or another distinct type. "
                "   - **DO NOT repeat any chart type**. Each visualization must use a unique technique (e.g., Histogram, Scatter, Boxplot, Heatmap, Contour, Violin, 3D Surface, Chord, Parallel Coordinates, etc.). "
                "   - **Diversity is mandatory**: Ensure maximum variety across all generated plots. "
                "### **1. Basic Statistical & Distribution Analysis**\n\n* Histogram\n* Box Plot (Box-and-Whisker Plot)\n* Violin Plot\n* Density Plot (Kernel Density Estimation - KDE)\n* Cumulative Distribution Function (CDF) Plot\n* Q-Q Plot (Quantile-Quantile Plot)\n* P-P Plot (Probability-Probability Plot)\n* Strip Plot\n* Swarm Plot\n* Rug Plot\n* Stem and Leaf Plot\n* Dot Plot\n* Pareto Chart\n\n### **2. Relationship & Correlation**\n\n* Scatter Plot\n* Bubble Chart\n* Pair Plot (Scatterplot Matrix)\n* Correlation Heatmap\n* Joint Plot\n* Marginal Plot\n* Mosaic Plot\n* Marimekko Chart\n* Connected Scatter Plot\n* Bland-Altman Plot\n\n### **3. Multivariate & High-Dimensional Data**\n\n* Parallel Coordinates Plot\n* Radar Chart (Spider Chart/Web Chart)\n* Ternary Plot (Simplex Plot)\n* Andrews Curves\n* Chernoff Faces\n* Biplot (PCA Visualization)\n* t-SNE Cluster Plot\n* UMAP Projection Plot\n\n### **4. Time Series & Change Over Time**\n\n* Line Chart\n* Area Chart\n* Stacked Area Chart\n* Streamgraph (ThemeRiver)\n* Step Chart\n* Candlestick Chart (OHLC)\n* Kagi Chart\n* Renko Chart\n* Horizon Chart\n* Spiral Plot\n* Autocorrelation Plot (ACF)\n* Partial Autocorrelation Plot (PACF)\n* Cross-Correlation Plot\n* Lag Plot\n* Spectral Density Plot (Periodogram)\n* Seasonal Decomposition Plot\n* Bump Chart\n* Slope Chart\n\n### **5. Comparison & Ranking**\n\n* Bar Chart (Grouped/Stacked)\n* Lollipop Chart\n* Dumbbell Plot\n* Bullet Graph\n* Radial Bar Chart\n* Funnel Chart\n* Waterfall Chart\n* Gauge Chart (Speedometer)\n* Pyramid Chart (e.g., Population Pyramid)\n* Word Cloud\n\n### **6. Part-to-Whole & Hierarchical**\n\n* Pie Chart\n* Donut Chart\n* Treemap\n* Sunburst Chart\n* Circle Packing\n* Dendrogram\n* Icicle Chart\n* Voronoi Diagram\n\n### **7. Network, Flow & Graph Theory**\n\n* Node-Link Diagram (Network Graph)\n* Adjacency Matrix\n* Sankey Diagram\n* Alluvial Diagram\n* Chord Diagram\n* Arc Diagram\n* Force-Directed Graph\n* Hive Plot\n* Non-Ribbon Chord Diagram\n* Spanning Tree Visualization\n\n### **8. Geospatial & Mapping**\n\n* Choropleth Map\n* Isopleth Map\n* Dot Density Map\n* Proportional Symbol Map (Bubble Map)\n* Flow Map\n* Connection Map\n* Hexbin Map\n* Cartogram (Dorling/Demers)\n* Heatmap (Geospatial)\n* Contour Map\n\n### **9. Dynamical Systems, Calculus & Physics**\n\n* Phase Portrait (Phase Plane Plot)\n* Vector Field Plot (Quiver Plot)\n* Streamline Plot (Streamplot)\n* Bifurcation Diagram\n* Cobweb Plot (Verhulst Diagram)\n* Poincaré Map\n* Trajectory Plot\n* Attractor Plot (e.g., Lorenz Attractor)\n* Slope Field\n* Nullclines Plot\n\n### **10. 3D & Surface Visualization**\n\n* 3D Scatter Plot\n* 3D Surface Plot\n* 3D Wireframe Plot\n* 3D Contour Plot\n* Isosurface\n* Mesh Plot\n* Triangular Mesh\n* Ribbon Plot\n\n### **11. Model Evaluation (Machine Learning & Statistics)**\n\n* Confusion Matrix\n* ROC Curve (Receiver Operating Characteristic)\n* Precision-Recall Curve\n* Lift Chart\n* Gain Chart\n* Learning Curve\n* Validation Curve\n* Elbow Plot (K-Means)\n* Silhouette Plot\n* Residual Plot\n* Feature Importance Plot\n* Decision Boundary Plot\n* Calibration Curve (Reliability Diagram)\n* Decision Tree Visualization\n\n### **12. Sensitivity Analysis & Uncertainty**\n\n* Tornado Diagram\n* Error Bar Plot\n* Confidence Interval Plot\n* Fan Chart (Fan Plot)\n* Ridgeline Plot (Joyplot)\n* Prediction Interval Plot\n\n### **13. Project Management & Process**\n\n* Gantt Chart\n* PERT Chart\n* Control Chart (Shewhart Chart)\n* Flowchart\n* Swimlane Diagram\n* State Transition Diagram\n\n---\n\nSelect about the **8** most suitable ones for drawing.\n\n\n"
                
                "2. **Multidimensionality**: Use visual depth to reveal latent patterns (e.g., phase transitions, sensitivity boundaries). "
                "3. **Aesthetic Rigor**: Adhere to academic publishing standards (high DPI, LaTeX-formatted labels). "
                "**DO NOT** re-calculate models; strictly **REUSE** existing data artifacts from previous steps."
            )
        }
    ),
    # [NEW] Node 2.4: Result
    # Summary of the current iteration's findings (Text Only)
    # Configuration matches 1.1 exactly (Generator + Markdown Viewer)
    NodeBlueprint(
        id="2.4",
        title="Result",
        phase_label="Phase 2: Modeling",
        node_type=NodeType.GENERATOR,
        templates={"generate": "nodes/2.4/generator.j2"},
        # Must participate in the Phase 2 iteration loop
        iteration=IterationStrategy(
            driver_node_id="1.3",
            driver_output_tag="sub_problem_list",
            context_slice_key="current_sub_task"
        ),
        # Interaction Policy matches 1.1
        interaction=InteractionPolicy(can_edit_content=True, can_reexecute=True),
        # UX Config matches 1.1 (Markdown Viewer, Standard Layout)
        ux=UXConfig(
            primary_view=RenderType.MARKDOWN_VIEWER,
            # Explicitly set to STANDARD to match 1.1's default behavior (Single Column)
            layout_mode=LayoutMode.STANDARD 
        )
    ),

    # Phase 3: Reporting (NEW ARCHITECTURE)
    # [Refactored] Phase 3 Architecture: Architect (3.1) -> Paper Writing (3.2).
    
    # Phase 3: Reporting
    # Node 3.1: The Architect (Generator)
    NodeBlueprint(
        id="3.1",
        title="Paper Outline",
        phase_label="Phase 3: Reporting",
        node_type=NodeType.GENERATOR,
        templates={"generate": "nodes/3.1/outline_gen.j2"},
        is_structural=True,
        # [FIX] Enable Editing
        interaction=InteractionPolicy(can_select_alternatives=True, can_reexecute=True, can_edit_content=True),
        ux=UXConfig(
            layout_mode=LayoutMode.SELECTION, 
            primary_view=RenderType.SCA_PLAN_CARD
        ),
        output_spec=OutputSpec(expected_type="json", target_label="outline")
    ),
    
    # Node 3.2: The Paper Writing (交付节点)
    # 这是一个 Native Executor，接管了原本 Writer/Editor/Publisher 的所有工作。
    # 也是用户唯一进行"编辑-编译"循环的地方。
    NodeBlueprint(
        id="3.2",
        title="Paper Writing",
        phase_label="Phase 3: Reporting",
        node_type=NodeType.EXECUTOR, 
        templates={},  # 逻辑由 Native Engine 接管
        meta={
            "executor_engine": "native_paper_engine",  # 路由标识
            "blueprint_source": "3.1",
            "manual_review_required": True,
            "agent_role": "LaTeX Editor",
            "agent_focus": "compilation",
            "primary_directive": (
                "Orchestrate the final **Manuscript Compilation**. "
                "Compile the structured LaTeX project into a pristine PDF document, ensuring typographic perfection, correct float placement, and citation integrity."
            )
        },
        interaction=InteractionPolicy(
            can_reexecute=True,    # 对应前端的 "Run" (Compile) 按钮
            can_edit_content=True, # 允许在编辑器中修改源码
            approval_required=True
        ),
        ux=UXConfig(
            layout_mode=LayoutMode.FOCUS,
            primary_view=RenderType.IDE_WORKSPACE,
            show_console=True,                   # 底部: 日志
            show_artifacts=True                  # 右侧: PDF
        ),
        output_spec=OutputSpec(expected_type="code", target_label="latex_source")
    )
]


class BlueprintRegistry:
    """
    Read-Only Registry for Workflow Topology.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._map = {b.id: b for b in _DEFAULTS}
            cls._instance._sequence = [b.id for b in _DEFAULTS]
            
            # Dynamically build Phase Index Map based on order of appearance
            # "Phase 1..." -> 0, "Phase 2..." -> 1, etc.
            cls._instance._phases = {}
            seen = set()
            idx = 0
            for b in _DEFAULTS:
                if b.phase_label not in seen:
                    cls._instance._phases[b.phase_label] = idx
                    seen.add(b.phase_label)
                    idx += 1
            
            # Define Serial Groups: Nodes within a group are executed serially across iterations
            # [UPDATED] Added "2.4" to the end of the chain so it receives context from 2.3
            cls._instance._serial_groups = {
                "Phase 2: Modeling": ["2.1", "2.2", "2.3", "2.4"]
            }
        return cls._instance

    def get(self, node_id: str) -> Optional[NodeBlueprint]:
        """Get a blueprint by ID."""
        return self._map.get(node_id)
    
    def get_all(self) -> List[NodeBlueprint]:
        """Get all blueprints in sequence order."""
        return [_DEFAULTS[i] for i, _ in enumerate(self._sequence)]

    def get_predecessors(self, node_id: str) -> List[str]:
        """
        Returns list of node IDs strictly before the target node.
        Used by ContextService to assemble upstream history.
        """
        try:
            idx = self._sequence.index(node_id)
            return self._sequence[:idx]
        except ValueError:
            return []

    def get_sequence_index(self, base_id: str) -> int:
        """Returns the index of the blueprint in the global sequence."""
        try:
            return self._sequence.index(base_id)
        except ValueError:
            return 999

    def get_global_index(self, base_id: str) -> int:
        """
        [NEW] Returns the static sequence index (0-based) used for linear visibility logic.
        This provides the absolute 'Timeline Position' of a blueprint.
        """
        return self.get_sequence_index(base_id)

    def get_phase_index(self, base_id: str) -> int:
        """
        Returns the Phase Index (0, 1, 2...) for robust sorting.
        """
        bp = self.get(base_id)
        if not bp: 
            return 99
        return self._phases.get(bp.phase_label, 99)

    def is_driver(self, node_id: str) -> bool:
        """[NEW] Checks if a node drives downstream topology expansion."""
        bp = self.get(node_id)
        return bp.is_structural if bp else False

    def get_dependents(self, driver_id: str) -> List[NodeBlueprint]:
        """[NEW] Returns all blueprints that iterate based on this driver."""
        return [
            bp for bp in self.get_all()
            if bp.iteration and bp.iteration.driver_node_id == driver_id
        ]

    def get_serial_group(self, base_id: str) -> Optional[List[str]]:
        """Returns the serial group ID list for a given base_id, if it belongs to one."""
        bp = self.get(base_id)
        if not bp: return None
        # Simple substring match for robustness
        for p_label, group in self._serial_groups.items():
            if p_label in bp.phase_label and base_id in group:
                return group
        return None


# Global Singleton
registry = BlueprintRegistry()
