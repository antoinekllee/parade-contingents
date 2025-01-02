from ortools.linear_solver import pywraplp
import csv
from datetime import datetime

def allocate_contingents(
    group_sizes,
    capacity,
    alpha=1.0,
    beta=5.0,
    use_all=True,
    fix_num_contingents=None
):
    """
    Solve the parade allocation problem using an Integer Linear Program (ILP) with OR-Tools.

    Args:
        group_sizes (dict): {group_label: number_of_people}, e.g. {'A':127, 'B':77, ...}.
        capacity (int): Target max size for each contingent (e.g. 90).
        alpha (float): Weight for penalizing underfilled seats (capacity - sum of x).
        beta (float): Weight for penalizing mixing (number of distinct groups in a contingent).
        use_all (bool): If True, forces all group members to be used. If False, allows partial usage.
        fix_num_contingents (int or None): If not None, enforce exactly this many contingents must be used. Otherwise, the solver decides.

    Returns:
        (contingents, objective_value) where:
         - contingents: a list of dicts, each {group_label: count_assigned}.
         - objective_value: the optimized objective value (lower is better).
    """
    # 1) Prepare data
    groups = list(group_sizes.keys())
    N = len(groups)
    A = [group_sizes[g] for g in groups]
    total_people = sum(A)

    # Estimate upper bound on # of contingents
    max_contingents = (total_people // capacity) + 3

    # 2) Create the solver
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        raise Exception("Could not create the OR-Tools solver.")

    # 3) Decision variables
    # x[i,c] = # of people from group i in contingent c
    # y[i,c] = 1 if group i is used in contingent c (x[i,c] > 0)
    x = {}
    y = {}
    BIG_M = capacity

    # z[c] = 1 if contingent c is actually used (i.e., sum_i x[i,c] > 0), else 0
    z = {}

    for c in range(max_contingents):
        z[c] = solver.BoolVar(f"z_{c}")

    for i in range(N):
        for c in range(max_contingents):
            x[(i, c)] = solver.IntVar(0, A[i], f"x_{i}_{c}")
            y[(i, c)] = solver.BoolVar(f"y_{i}_{c}")

    # 4) Constraints

    # 4a) Capacity: Each contingent can't exceed the target size (sum_i x[i,c] <= capacity)
    for c in range(max_contingents):
        solver.Add(
            sum(x[(i, c)] for i in range(N)) <= capacity * z[c]
        )

    # Also ensure if z[c] = 1, sum_i x[i,c] >= 1 (so the contingent can't be "used" if it's empty)
    for c in range(max_contingents):
        solver.Add(
            sum(x[(i, c)] for i in range(N)) >= z[c]
        )

    # 4b) Each group's total usage
    for i in range(N):
        if use_all:
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) == A[i])
        else:
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) <= A[i])

    # 4c) Linking x and y: x[i,c] <= BIG_M * y[i,c]
    for i in range(N):
        for c in range(max_contingents):
            solver.Add(x[(i, c)] <= BIG_M * y[(i, c)])

    # 4d) If we fix the total # of contingents used, sum_c z[c] = fix_num_contingents
    if fix_num_contingents is not None:
        solver.Add(solver.Sum([z[c] for c in range(max_contingents)]) == fix_num_contingents)

    # 5) Build the objective expression
    # We'll sum over c of [ alpha * underfill_c + beta * mixing_c ], where:
    #   underfill_c = (capacity - sum_i x[i,c]) if z[c] = 1, else 0
    #   mixing_c = sum_i y[i,c]
    # We'll do it with solver.Sum(...) to avoid the "SetCoefficient" limitations.

    objective_terms = []
    # The solver tries to minimize two things: 
    # 1) Underfilling: Having contingents smaller than the capacity (weighted by alpha)
    # 2) Mixing: Having multiple groups in a contingent (weighted by beta)
    for c in range(max_contingents):
        # underfill_c
        underfill_c = capacity * z[c] - solver.Sum([x[(i, c)] for i in range(N)])
        # mixing_c = sum of y[i,c]
        mixing_c = solver.Sum([y[(i, c)] for i in range(N)])
        # combine them
        objective_terms.append(alpha * underfill_c + beta * mixing_c)

    total_objective_expr = solver.Sum(objective_terms)
    solver.Minimize(total_objective_expr)

    # 6) Solve
    status = solver.Solve()
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise Exception("No feasible solution found by the solver.")

    # 7) Extract solution
    contingents = []
    for c in range(max_contingents):
        assigned_sum = sum(int(x[(i, c)].solution_value()) for i in range(N))
        if assigned_sum == 0:
            continue  # skip empty
        cont_dict = {}
        for i in range(N):
            val = int(x[(i, c)].solution_value())
            if val > 0:
                cont_dict[groups[i]] = val
        contingents.append(cont_dict)

    return contingents, solver.Objective().Value()


def main():
    group_sizes = { 
        'Inf (1)': 127,
        'Navy': 77,
        'Air Force': 30,
        'DIS': 112,
        'IDTI': 86,
        'CSSCOM': 135,
        'ETI': 117,
        'AI': 12,
        'ATI': 44,
        'SI': 107,
        'SMI-I': 46,
        'Inf (2)': 113,
    }
    capacity = 90 # Target max size for each contingent
    total_people = sum(group_sizes.values()) # Total number of people to assign

    # Objective weighting
    alpha = 1.0 # Penalizes undersized contingents
    beta = 5.0 # Penalizes mixing of different groups

    fix_num_contingents = 12 # Exactly 12 contingents

    contingents, obj_val = allocate_contingents(
        group_sizes=group_sizes,
        capacity=capacity,
        alpha=alpha,
        beta=beta,
        use_all=True,
        fix_num_contingents=fix_num_contingents
    )

    # Print results
    print("=========================================")
    print(" Parade Allocation ILP Solver (OR-Tools) ")
    print("=========================================")
    print(f"Total people: {total_people}")
    print(f"Contingent capacity: {capacity}")
    if fix_num_contingents is not None:
        print(f"Exact number of contingents used: {fix_num_contingents}")
    else:
        print(f"No fixed number of contingents; solver decides.")

    print(f"\nObjective value: {obj_val:.2f} (lower = better)")
    print(f"(alpha={alpha}, beta={beta})\n")

    grand_total_assigned = 0
    for idx, cont in enumerate(contingents, start=1):
        total_in_cont = sum(cont.values())
        letters_used = len(cont)
        groups_list = ", ".join(f"{g}:{n}" for g, n in cont.items())
        print(f"Contingent #{idx}: total={total_in_cont}, #groups={letters_used}")
        print(f"   -> {groups_list}")
        grand_total_assigned += total_in_cont

    print("\n-----------------------------------------")
    print(f"Number of contingents used: {len(contingents)}")
    print(f"Grand total assigned: {grand_total_assigned}")
    print("All group members are assigned exactly once (use_all=True).")
    print("=========================================")

    # Prepare CSV output
    timestamp = datetime.now().strftime("%d%m%y_%H%M%S")
    csv_filename = f"output/parade_allocation_{timestamp}.csv"

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header information
        writer.writerow(['Parade Allocation Results'])
        writer.writerow(['Generated on', datetime.now().strftime("%d%m%y %H:%M")])
        writer.writerow([])
        writer.writerow(['Total People', total_people])
        writer.writerow(['Contingent Capacity', capacity])
        writer.writerow(['Objective Value', f"{obj_val:.2f}"])
        writer.writerow(['Alpha', alpha])
        writer.writerow(['Beta', beta])
        writer.writerow([])
        
        # Write contingent details header - reordered columns
        writer.writerow(['Contingent #', 'Total People', 'Group Assignments', 'Number of Groups'])
        
        # Write each contingent's details - reordered columns
        for idx, cont in enumerate(contingents, start=1):
            total_in_cont = sum(cont.values())
            letters_used = len(cont)
            groups_list = ", ".join(f"{g}:{n}" for g, n in cont.items())
            writer.writerow([idx, total_in_cont, groups_list, letters_used])
        
        # Write summary
        writer.writerow([])
        writer.writerow(['Summary Statistics'])
        writer.writerow(['Total Contingents Used', len(contingents)])
        writer.writerow(['Total People Assigned', grand_total_assigned])
        writer.writerow(['All Members Assigned', 'Yes' if True else 'No'])

    print("\nResults have been saved to:", csv_filename)

if __name__ == "__main__":
    main()
