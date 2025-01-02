#!/usr/bin/env python3
from ortools.linear_solver import pywraplp
import csv
from datetime import datetime

def allocate_contingents(group_sizes, capacity, alpha=1.0, beta=5.0, use_all=True):
    """
    Solve the parade allocation problem using an Integer Linear Program (ILP) with OR-Tools.

    Args:
        group_sizes (dict): {group_label: number_of_people}, e.g. {'A':127, 'B':77, ...}.
        capacity (int): Target max size for each contingent (e.g. 90).
        alpha (float): Weight for penalizing underfilled seats (capacity - sum of x).
        beta (float): Weight for penalizing mixing (number of distinct groups in a contingent).
        use_all (bool): If True, forces all group members to be used. If False, allows partial usage.

    Returns:
        (contingents, objective_value) where:
         - contingents: a list of dicts, each {group_label: count_assigned} for a contingent.
         - objective_value: the optimized objective value (lower is better).
    """
    # 1) Prepare data
    groups = list(group_sizes.keys())
    N = len(groups)
    A = [group_sizes[g] for g in groups]
    total_people = sum(A)

    # Estimate upper bound on # of contingents we might use
    max_contingents = (total_people // capacity) + 3

    # 2) Create the solver
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        raise Exception("Could not create the OR-Tools solver.")

    # 3) Decision variables
    x = {}  # x[(i, c)] = # of people from group i in contingent c
    y = {}  # y[(i, c)] = 1 if group i is used in contingent c, else 0
    BIG_M = capacity

    for i in range(N):
        for c in range(max_contingents):
            x[(i, c)] = solver.IntVar(0, A[i], f"x_{i}_{c}")
            y[(i, c)] = solver.BoolVar(f"y_{i}_{c}")

    # 4) Constraints

    # 4a) Capacity: sum_i x[i,c] <= capacity for each contingent c
    for c in range(max_contingents):
        solver.Add(
            sum(x[(i, c)] for i in range(N)) <= capacity
        )

    # 4b) Group usage: sum_c x[i,c] == A[i] (use all) or <= A[i] (if partial usage is allowed)
    for i in range(N):
        if use_all:
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) == A[i])
        else:
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) <= A[i])

    # 4c) Linking: x[i,c] <= BIG_M * y[i,c]
    for i in range(N):
        for c in range(max_contingents):
            solver.Add(x[(i, c)] <= BIG_M * y[(i, c)])

    # 5) Build the objective expression
    #    We'll create an expression for each contingent:
    #        underfill_c = capacity - sum_i x[i,c]
    #        mixing_c = sum_i y[i,c]
    #    and add alpha*underfill_c + beta*mixing_c to the objective.

    objective_terms = []
    for c in range(max_contingents):
        # underfill expression
        underfill_c = capacity - solver.Sum([x[(i, c)] for i in range(N)])
        # mixing expression
        mixing_c = solver.Sum([y[(i, c)] for i in range(N)])

        # alpha * underfill_c + beta * mixing_c
        objective_terms.append(alpha * underfill_c + beta * mixing_c)

    # Combine all contingents' terms into one expression
    total_objective_expr = solver.Sum(objective_terms)

    # 6) Solve (Minimize the objective)
    solver.Minimize(total_objective_expr)
    status = solver.Solve()
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise Exception("No feasible solution found by the solver.")

    # 7) Extract solution
    contingents = []
    for c in range(max_contingents):
        assigned_sum = sum(int(x[(i, c)].solution_value()) for i in range(N))
        if assigned_sum == 0:
            continue  # No one assigned => skip

        cont_dict = {}
        for i in range(N):
            val = int(x[(i, c)].solution_value())
            if val > 0:
                cont_dict[groups[i]] = val
        contingents.append(cont_dict)

    obj_value = solver.Objective().Value()
    return contingents, obj_value


def main():
    # -------------------------
    # Input data (A through L)
    # -------------------------
    group_sizes = {
        'A': 127,
        'B': 77,
        'C': 30,
        'D': 112,
        'E': 86,
        'F': 135,
        'G': 117,
        'H': 12,
        'I': 44,
        'J': 107,
        'K': 46,
        'L': 113,
    }
    capacity = 90
    total_people = sum(group_sizes.values())

    # Adjust alpha / beta to tweak the solver's priorities:
    #  - alpha penalizes "underfill" => how far a contingent is from 90
    #  - beta penalizes "mixing" => how many groups go into the same contingent
    alpha = 1.0
    beta = 5.0

    contingents, obj_val = allocate_contingents(
        group_sizes=group_sizes,
        capacity=capacity,
        alpha=alpha,
        beta=beta,
        use_all=True
    )

    print("=========================================")
    print(" Parade Allocation ILP Solver (OR-Tools) ")
    print("=========================================")
    print(f"Total people: {total_people}")
    print(f"Contingent capacity: {capacity}")
    print(f"Objective value: {obj_val:.2f} (lower = better)")
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
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"parade_allocation_{timestamp}.csv"

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header information
        writer.writerow(['Parade Allocation Results'])
        writer.writerow(['Generated on', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])
        writer.writerow(['Total People', total_people])
        writer.writerow(['Contingent Capacity', capacity])
        writer.writerow(['Objective Value', f"{obj_val:.2f}"])
        writer.writerow(['Alpha', alpha])
        writer.writerow(['Beta', beta])
        writer.writerow([])
        
        # Write contingent details header
        writer.writerow(['Contingent #', 'Total People', 'Number of Groups', 'Group Assignments'])
        
        # Write each contingent's details
        for idx, cont in enumerate(contingents, start=1):
            total_in_cont = sum(cont.values())
            letters_used = len(cont)
            groups_list = ", ".join(f"{g}:{n}" for g, n in cont.items())
            writer.writerow([idx, total_in_cont, letters_used, groups_list])
        
        # Write summary
        writer.writerow([])
        writer.writerow(['Summary Statistics'])
        writer.writerow(['Total Contingents Used', len(contingents)])
        writer.writerow(['Total People Assigned', grand_total_assigned])
        writer.writerow(['All Members Assigned', 'Yes (use_all=True)'])

    print("\nResults have been saved to:", csv_filename)


if __name__ == "__main__":
    main()
