# Parade Contingent Allocation Solver

## Overview
This project provides an optimization solution for allocating military parade participants into balanced contingents while minimizing group mixing and maintaining target sizes. The solver uses Integer Linear Programming (ILP) to find the optimal allocation that satisfies multiple constraints and objectives.

## Problem Statement
Given multiple groups of participants (e.g., Infantry, Navy, Air Force), the solver aims to:
- Organize participants into contingents of approximately equal size
- Minimize mixing of different groups within each contingent
- Avoid creating undersized contingents
- Ensure all participants are assigned

### Key Objectives
1. Maintain contingent sizes close to target capacity (but not above it)
2. Minimize the number of different groups in each contingent
3. Avoid creating a "leftover" contingent with many mixed groups

## Installation

### Prerequisites
```bash
pip install ortools
```

### Required Dependencies
- Google OR-Tools
- Python 3.7+
- CSV module (built-in)
- datetime module (built-in)

## Usage

### Basic Example
```python
group_sizes = {
    'Infantry': 127,
    'Navy': 77,
    'Air Force': 30,
    # ... more groups ...
}

contingents, objective_value = allocate_contingents(
    group_sizes=group_sizes,
    capacity=90,
    alpha=1.0,
    beta=5.0,
    use_all=True,
    fix_num_contingents=12
)
```

### Parameters
- `group_sizes`: Dictionary mapping group names to their sizes
- `capacity`: Target size for each contingent
- `alpha`: Weight for penalizing undersized contingents (default: 1.0)
- `beta`: Weight for penalizing group mixing (default: 5.0)
- `use_all`: Whether all participants must be assigned (default: True)
- `fix_num_contingents`: Force exact number of contingents (optional)

## Output
The solver produces:
1. Console output with detailed allocation results
2. CSV file with:
   - Summary statistics
   - Detailed contingent assignments
   - Configuration parameters
   - Timestamp

### Sample Output Format
```
Contingent #1: total=88, #groups=2
   -> Inf (1):65, Navy:23

Contingent #2: total=90, #groups=1
   -> CSSCOM:90
...
```

## Technical Details

### Parameter Tuning
The solver's behavior can be controlled through two parameters.

#### Alpha (α)
- Penalizes undersized contingents
- Higher values (α > 1.0) enforce stricter size requirements
- Default: 1.0

#### Beta (β)
- Penalizes mixing of different groups
- Higher values (β > 5.0) strongly favor single-group contingents
- Default: 5.0

## Output Files
Results are saved in `output/parade_allocation_DDMMYY_HHMMSS.csv` with:
- Configuration parameters
- Detailed assignments
- Summary statistics
- Timestamp of generation