# Parade Contingent Allocation Solver

## Overview
This project provides an optimization solution for allocating military parade participants into balanced contingents while minimizing group mixing and maintaining target sizes. The solver uses Integer Linear Programming (ILP) to find the optimal allocation that satisfies multiple constraints and objectives.

## Problem Statement
Given multiple groups of participants (e.g., Infantry, Navy, Air Force), the solver aims to:
- Organize participants into contingents of approximately equal size
- **Pre-allocate** certain groups (if marked with `avoid_split`) into their own contingents or partial contingents
- Minimize mixing of different groups within each contingent
- Avoid creating undersized contingents (enforced by a **strict minimum** capacity)
- Enforce multiples of a specified row size (e.g., multiples of 5) for certain groups
- Ensure all participants are assigned (if `use_all=True`)

### Key Objectives
1. Maintain contingent sizes close to target capacity (but not above it)
2. Minimize the number of different groups in each contingent
3. Avoid creating a "leftover" contingent with many mixed groups
4. Respect the strict minimum contingent size (to ensure no contingent is too small)

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
    'Infantry': {'size': 127, 'avoid_split': True},
    'Navy':     {'size': 77,  'avoid_split': True},
    'Air Force':{'size': 30,  'avoid_split': True},
    # ... more groups ...
}

contingents, objective_value = allocate_contingents(
    group_sizes=group_sizes,
    capacity=90,
    strict_min_capacity=70,
    alpha=1.0,
    beta=5.0,
    use_all=True,
    fix_num_contingents=12,
    contingent_row_size=5
)
```

### Parameters
- **group_sizes**:  
  Dictionary mapping group names to a dictionary of `{ 'size': <int>, 'avoid_split': <bool> }`.  
  Example:  
  ```python
  {
      'Inf (1)':  {'size': 127, 'avoid_split': True},
      'Navy':     {'size': 77,  'avoid_split': True},
      ...
  }
  ```
- **capacity**:  
  Target size (maximum) for each contingent.
- **strict_min_capacity**:  
  Strict minimum size for each used contingent (no contingent should be smaller than this if it’s used).
- **contingent_row_size**:  
  If a group has `avoid_split=True` **and** its size is less than `capacity`, the sum of all people in the contingent chosen for that group must be a multiple of `contingent_row_size` (e.g., multiples of 5).  
- **alpha**:  
  Weight for penalizing undersized contingents. (Default: 1.0)
- **beta**:  
  Weight for penalizing mixing (number of distinct groups in a contingent). (Default: 5.0)
- **use_all**:  
  Whether all participants must be assigned. (Default: True)
- **fix_num_contingents**:  
  Force an exact number of contingents. If `None`, the solver decides how many contingents to use. (Default: `12` in the sample code)
- **time_limit**:  
  Maximum solver time in seconds. (Default: 60)

## Output
The solver produces:
1. Console output with detailed allocation results
2. A CSV file with:
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

## Constraints

Below are the main constraints enforced by the solver (labeled as in the code). We also include the relevant lines from the code and a brief explanation of what each constraint does:

---

### 4a) Capacity  
**Line of code** (abbreviated):
```python
solver.Add(sum(x[(i, c)] for i in range(N)) <= capacity * z[c])
solver.Add(sum(x[(i, c)] for i in range(N)) >= z[c])
```
**Explanation**:  
These constraints ensure that each contingent cannot exceed its maximum capacity and that if a contingent is used, it has at least one person.

---

### 4b) Group Usage  
**Line of code** (abbreviated):
```python
if use_all:
    solver.Add(sum(x[(i, c)] for c in range(max_contingents)) == A[i])
else:
    solver.Add(sum(x[(i, c)] for c in range(max_contingents)) <= A[i])
```
**Explanation**:  
These constraints control whether each group’s entire size must be used (if `use_all=True`) or if partial usage is allowed (if `use_all=False`).

---

### 4c) Linking x and y  
**Line of code** (abbreviated):
```python
solver.Add(x[(i, c)] <= BIG_M * y[(i, c)])
```
**Explanation**:  
This ensures that if a group is assigned to a contingent, it is marked as present in that contingent.

---

### 4d) Fixed Number of Contingents  
**Line of code** (abbreviated):
```python
if fix_num_contingents is not None:
    solver.Add(solver.Sum([z[c] for c in range(max_contingents)]) == fix_num_contingents)
```
**Explanation**:  
This constraint makes sure the solver uses exactly the specified number of contingents if required.

---

### 4e) Handling `avoid_split` and Multiples of `contingent_row_size`  
**Line of code** (abbreviated):
```python
if avoid_split and original_size < capacity:
    solver.Add(solver.Sum([y[(i, c)] for c in range(max_contingents)]) == 1)
    ...
    solver.Add(sum_c - contingent_row_size * m[(i, c)] <= BIG_M_2 * (1 - y[(i, c)]))
    solver.Add(sum_c - contingent_row_size * m[(i, c)] >= -BIG_M_2 * (1 - y[(i, c)]))
```
**Explanation**:  
If a group should not be split and is smaller than the capacity, it is placed in exactly one contingent, and the total people in that contingent must be a multiple of the chosen row size.

---

### 4f) Strict Minimum Capacity  
**Line of code** (abbreviated):
```python
solver.Add(sum(x[(i, c)] for i in range(N)) >= strict_min_capacity * z[c])
```
**Explanation**:  
This constraint makes sure that any contingent used has at least the strict minimum number of people.

---

## Technical Details

### Pre-allocation
Certain groups may be **pre-allocated** before the ILP begins if they have `avoid_split=True` and their size is larger than or equal to `capacity`. In that scenario, we create as many full contingents as possible (each exactly `capacity` in size), and only leave a remainder for the solver if there's anything left over. This feature helps reduce complexity and respects the requirement that some groups must remain intact without splitting across contingents.

### Parameter Tuning
The solver's behavior can be controlled through two main parameters.

#### Alpha (α)
- Penalizes undersized contingents.  
- Higher values (α > 1.0) enforce stricter size requirements.  
- Default: 1.0

#### Beta (β)
- Penalizes mixing of different groups within each contingent.  
- Higher values (β > 5.0) strongly favor single-group contingents.  
- Default: 5.0

## Output Files
Results are saved in `output/parade_allocation_DDMMYY_HHMMSS.csv` with:
- Configuration parameters
- Detailed assignments
- Summary statistics
- Timestamp of generation

## Example
```bash
python solve_parade.py
```
After running, the console displays the solution, and a CSV is written to the `output/` folder.