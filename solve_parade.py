from ortools.linear_solver import pywraplp

def allocate_contingents(group_sizes, capacity, alpha=1.0, beta=5.0, use_all=True):
    """
    Solve the parade allocation problem using an Integer Linear Program (ILP) with OR-Tools.

    Args:
        group_sizes (dict): {group_label: number_of_people}, e.g. {'A': 127, 'B': 77, ...}.
        capacity (int): Target max size for each contingent (e.g. 90).
        alpha (float): Weight for penalizing underfilled seats.
        beta (float): Weight for penalizing mixing (# of groups in a contingent).
        use_all (bool): If True, forces all group members to be used. If False, allows leaving some people unused.

    Returns:
        (contingent_assignments, objective_value) where:
         - contingent_assignments: a list of dicts, each dict {group_label: count_assigned}.
         - objective_value: value of the objective function for the returned solution.
    """

    groups = list(group_sizes.keys())
    N = len(groups)
    A = [group_sizes[g] for g in groups]
    total_people = sum(A)

    # Estimate a reasonable upper bound on the number of contingents needed.
    # If each contingent is fully filled (size=capacity), we'd need total_people // capacity contingents, 
    # plus a few extra to allow underfilling flexibility.
    max_contingents = (total_people // capacity) + 3

    # Create the solver (SCIP can handle MILP problems).
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        raise Exception("Could not create the OR-Tools solver.")

    # Decision variables:
    # x[i,c] = integer # of people from group i in contingent c
    # y[i,c] = binary indicator: 1 if x[i,c] > 0, else 0
    x = {}
    y = {}
    BIG_M = capacity  # A safe upper bound for x[i,c], can also use max(A) if desired.

    for i in range(N):
        for c in range(max_contingents):
            x[(i, c)] = solver.IntVar(0, A[i], f"x_{i}_{c}")
            y[(i, c)] = solver.BoolVar(f"y_{i}_{c}")

    # Constraints

    # 1) Capacity for each contingent c: sum over i of x[i,c] <= capacity
    for c in range(max_contingents):
        solver.Add(
            sum(x[(i, c)] for i in range(N)) <= capacity
        )

    # 2) Each group's total usage <= (or ==) group size
    for i in range(N):
        if use_all:
            # Force using all members of group i
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) == A[i])
        else:
            # Allow partial usage
            solver.Add(sum(x[(i, c)] for c in range(max_contingents)) <= A[i])

    # 3) Linking constraint: x[i,c] <= BIG_M * y[i,c]
    for i in range(N):
        for c in range(max_contingents):
            solver.Add(x[(i, c)] <= BIG_M * y[(i, c)])

    # Define expressions for underfill and mixing
    underfill_expr = {}
    mixing_expr = {}
    for c in range(max_contingents):
        # how many seats are unused in contingent c
        underfill_expr[c] = capacity - sum(x[(i, c)] for i in range(N))
        # how many distinct groups appear in contingent c
        mixing_expr[c] = sum(y[(i, c)] for i in range(N))

    # Objective: minimize alpha * sum(underfill) + beta * sum(mixing)
    objective = solver.Objective()
    for c in range(max_contingents):
        objective.SetCoefficient(underfill_expr[c], alpha)
        objective.SetCoefficient(mixing_expr[c], beta)
    objective.SetMinimization()

    # Solve
    status = solver.Solve()
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise Exception("No feasible solution found by the solver.")

    # Build the final list of contingents from solver decisions
    contingents = []
    for c in range(max_contingents):
        assigned_sum = sum(int(x[(i, c)].solution_value()) for i in range(N))
        if assigned_sum == 0:
            # No one assigned to this contingent => skip
            continue
        cont_dict = {}
        for i in range(N):
            val = int(x[(i, c)].solution_value())
            if val > 0:
                cont_dict[groups[i]] = val
        contingents.append(cont_dict)

    # Return the final solution (list of dicts) and the objective value
    return contingents, solver.Objective().Value()


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
    capacity = 90  # Desired max size per contingent

    # We choose alpha and beta to reflect:
    # - alpha = 1: each unused seat in a contingent has a cost of 1
    # - beta = 5: each group present in a contingent adds a cost of 5
    # 
    # This means we prioritize fewer groups per contingent more strongly than perfect filling,
    # but still care about not leaving huge underfill.
    alpha = 1.0
    beta = 5.0

    solution, obj_val = allocate_contingents(
        group_sizes, 
        capacity, 
        alpha=alpha, 
        beta=beta, 
        use_all=True
    )

    # Print results
    print("=========================================")
    print(" Parade Allocation Solution (ILP) ")
    print("=========================================")
    print(f"Total people: {sum(group_sizes.values())}")
    print(f"Contingent capacity: {capacity}")
    print(f"Objective value: {obj_val:.2f}")
    print(f"(Lower objective => better. alpha={alpha}, beta={beta})\n")

    grand_total_assigned = 0
    for idx, cont in enumerate(solution, start=1):
        total_people_in_cont = sum(cont.values())
        letters_used = len(cont)
        letter_list = ", ".join(f"{g}:{n}" for g,n in cont.items())
        print(f"Contingent #{idx}: total={total_people_in_cont} (capacity={capacity}), #letters={letters_used}")
        print(f"   -> {letter_list}")
        grand_total_assigned += total_people_in_cont

    print("\n-----------------------------------------")
    print(f"Number of contingents used: {len(solution)}")
    print(f"Grand total assigned: {grand_total_assigned}")
    print("All group members are assigned exactly once.")
    print("=========================================")


if __name__ == "__main__":
    main()
