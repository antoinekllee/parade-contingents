from ortools.linear_solver import pywraplp
import csv
from datetime import datetime
import json
from pathlib import Path
from halo import Halo
from termcolor import colored
import time
from threading import Thread

def load_config():
    """Load configuration from input.json if it exists, otherwise return defaults."""
    defaults = {
        "contingent_row_size": 5,
        "capacity": 85,
        "strict_min_capacity": 70,
        "group_sizes": {
            'Inf (1)':  {'size': 127, 'avoid_split': True},
            'Inf (2)':  {'size': 113, 'avoid_split': True},
            'Navy':     {'size': 77, 'avoid_split': True},
            'Air Force': {'size': 30, 'avoid_split': True},
            'DIS':      {'size': 112, 'avoid_split': True},
            'IDTI':     {'size': 86, 'avoid_split': False},
            'CSSCOM':   {'size': 135, 'avoid_split': False},
            'ETI':      {'size': 117, 'avoid_split': False},
            'AI':       {'size': 12, 'avoid_split': False},
            'ATI':      {'size': 44, 'avoid_split': False},
            'SI':       {'size': 107, 'avoid_split': False},
            'SMI-I':    {'size': 46, 'avoid_split': False}
        },
        "alpha": 1.0,
        "beta": 5.0,
        "fix_num_contingents": 12,
        "time_limit": 60
    }

    try:
        config_path = Path("input.json")
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Update defaults with any values from the JSON file
                defaults.update(config)
                print("Configuration loaded from input.json")
        else:
            print("No input.json found, using default values")
    except Exception as e:
        print(f"Error reading input.json: {e}")
        print("Using default values")

    return defaults

def allocate_contingents(
    group_sizes,
    capacity,
    strict_min_capacity,
    contingent_row_size=5,
    alpha=1.0,
    beta=5.0,
    use_all=True,
    fix_num_contingents=None,
    time_limit=60
):
    """
    Solve the parade allocation problem using an Integer Linear Program (ILP) with OR-Tools. Certain groups may be pre-chunked into their own full or partial contingents if marked with a special flag (e.g., 'avoid_split' = True).
    
    Additionally, if 'avoid_split' is True AND a group's size is less than 'capacity', that group is forced to occupy exactly one contingent, and that contingent must be completely filled (i.e., equal to capacity) given a multiple of contingent_row_size.
    
    Args:
        group_sizes (dict): A dict of the form:
            {
                'GroupName': {
                    'size': <int>,
                    'avoid_split': <bool>
                },
                ...
            }
        capacity (int): Target max size for each contingent (e.g. 85).
        contingent_row_size (int): Number of rows in each contingent (default=5). Used to calculate acceptable partial contingent sizes.
        alpha (float): Weight for penalizing underfilled seats (capacity - sum of x).
        beta (float): Weight for penalizing mixing (number of distinct groups in a contingent).
        use_all (bool): If True, forces all group members to be used. If False, allows partial usage.
        fix_num_contingents (int or None): If not None, enforce exactly this many contingents must be used. Otherwise, the solver decides.

    Returns:
        (contingents, objective_value) where:
         - contingents: a list of dicts, each {group_label: count_assigned}.
         - objective_value: the optimized objective value (lower is better).
    """
    start_time = time.time()
    spinner = Halo(text='', spinner='dots')
    current_message = ['']  # Using list to allow modification in closure
    
    # Thread function to update spinner text
    def update_time():
        while spinner.spinner_id: # while spinner active
            elapsed = time.time() - start_time
            spinner.text = f"{current_message[0]} ({elapsed:.2f}s)"
            time.sleep(0.1) 
    
    # Update spinner message (without affecting the time update)
    def update_spinner(message):
        current_message[0] = message
    
    spinner.start()
    update_thread = Thread(target=update_time, daemon=True)
    update_thread.start()

    try:
        # Update spinner text with elapsed time
        def update_spinner(message):
            elapsed = time.time() - start_time
            spinner.text = f"{message} ({elapsed:.2f}s)"

        # 1) Pre-allocate contingents for groups marked "avoid_split"
        print(colored("\n[1/5] Pre-allocating contingents marked 'avoid_split'...", 'cyan'))
        update_spinner('Pre-allocating contingents...')
        pre_allocated_contingents = []
        remaining_group_sizes = {}

        for g, info in group_sizes.items():
            group_count = info["size"]
            avoid_split = info.get("avoid_split", False)

            if avoid_split and group_count > 0:
                # Create as many full contingents of 'capacity' as we can
                while group_count >= capacity:
                    pre_allocated_contingents.append({g: capacity})
                    group_count -= capacity
                
                # If there's a leftover smaller than capacity
                if group_count > 0:
                    # That leftover portion still needs to be allocated by the solver
                    remaining_group_sizes[g] = group_count
            else:
                # If not avoid_split or group_count==0, 
                # just feed the entire group_count to the solver.
                remaining_group_sizes[g] = group_count

        # If user wants a fixed number of contingents, subtract out the contingents we already used from pre_allocated_contingents
        if fix_num_contingents is not None:
            used_pre = len(pre_allocated_contingents)
            # Ensure the solver doesn't go negative in how many it can create:
            fix_num_contingents = max(0, fix_num_contingents - used_pre)

        # Make an easy list of groups and their sizes
        groups = list(remaining_group_sizes.keys())
        A = [remaining_group_sizes[g] for g in groups]
        total_people = sum(A)

        # If everything was pre-allocated (i.e. total_people=0), 
        # then just return the pre-allocated contingents and 0 objective
        if total_people == 0:
            return pre_allocated_contingents, 0

        N = len(groups)
        # Provide a small buffer on max number of contingents
        max_contingents = (total_people // capacity) + 3

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Pre-allocation complete ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Setting up ILP solver...')
        print(colored("\n[2/5] Configuring solver variables and constraints...", 'cyan'))

        # Create the solver
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            raise Exception("Could not create the OR-Tools solver.")
        
        solver.SetTimeLimit(time_limit * 1000)  # time_limit in seconds

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Solver created ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Creating decision variables...')

        # Decision variables
        # x[i,c] = # of people from group i in contingent c
        # y[i,c] = 1 if group i is used in contingent c (x[i,c] > 0)
        # z[c] = 1 if contingent c is actually used (i.e., sum_i x[i,c] > 0), else 0
        x = {}
        y = {}
        z = {}
        BIG_M = capacity

        for c in range(max_contingents):
            z[c] = solver.BoolVar(f"z_{c}")

        for i in range(N):
            for c in range(max_contingents):
                x[(i, c)] = solver.IntVar(0, A[i], f"x_{i}_{c}")
                y[(i, c)] = solver.BoolVar(f"y_{i}_{c}")

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Decision variables created ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Adding constraints...')
        print(colored("\n[3/5] Adding constraints to the model...", 'cyan'))
        
        # Constraints
        # 4a) Capacity: Each contingent can't exceed the target size (sum_i x[i,c] <= capacity)
        for c in range(max_contingents):
            solver.Add(sum(x[(i, c)] for i in range(N)) <= capacity * z[c])

        # Also ensure if z[c] = 1, sum_i x[i,c] >= 1 (so the contingent can't be "used" if it's empty)
        for c in range(max_contingents):
            solver.Add(sum(x[(i, c)] for i in range(N)) >= z[c])

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

        # 4d) If we fix the total # of contingents, sum_c z[c] = fix_num_contingents
        if fix_num_contingents is not None:
            solver.Add(solver.Sum([z[c] for c in range(max_contingents)]) == fix_num_contingents)

        # 4e) If avoid_split=True AND size < capacity, then that group must occupy exactly 1 contingent. In that chosen contingent, the total assigned is forced to be a multiple of contingent_row_size=5.

        # Dictionary "m" will hold the new integer variables:
        m = {}

        for i in range(N):
            g_name = groups[i]
            original_size = group_sizes[g_name]["size"]
            avoid_split = group_sizes[g_name].get("avoid_split", False)

            if avoid_split and original_size < capacity:
                # Force this group to appear in exactly one contingent
                solver.Add(solver.Sum([y[(i, c)] for c in range(max_contingents)]) == 1)
                
                for c in range(max_contingents):
                    # Create an integer variable m_{i,c} for enforcing multiples of 5
                    m[(i, c)] = solver.IntVar(0, capacity, f"m_{i}_{c}")

                    # sum_c is the total # of people in contingent c
                    sum_c = solver.Sum(x[(i_prime, c)] for i_prime in range(N))

                    # Big-M approach:
                    # If y_{(i,c)}=1, then sum_c = 5 * m_{(i,c)}.
                    # If y_{(i,c)}=0, no restriction is imposed (sum_c - 5*m_{(i,c)} can be anything).
                    BIG_M_2 = capacity  # Enough to cover all feasible sums

                    solver.Add(sum_c - contingent_row_size * m[(i, c)] <= BIG_M_2 * (1 - y[(i, c)]))
                    solver.Add(sum_c - contingent_row_size * m[(i, c)] >= -BIG_M_2 * (1 - y[(i, c)]))

        # 4f) Enforce minimum capacity for each used contingent
        for c in range(max_contingents):
            solver.Add(sum(x[(i, c)] for i in range(N)) >= strict_min_capacity * z[c])

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Constraints added ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Setting up objective function...')
        print(colored("\n[4/5] Setting up objective function...", 'cyan'))
        
        # 5) Objective

        # The solver tries to minimize two things: 
        # 1) Underfilling: Having contingents smaller than the capacity (weighted by alpha)
        # 2) Mixing: Having multiple groups in a contingent (weighted by beta)
        
        # Minimize [ alpha * underfill_c + beta * mixing_c ]
        #   underfill_c = capacity - sum_i x[i,c] for each used c
        #   mixing_c = sum_i y[i,c] (# distinct groups in c)
        
        objective_terms = []
        for c in range(max_contingents):
            # underfill_c
            underfill_c = capacity * z[c] - solver.Sum([x[(i, c)] for i in range(N)])
            # mixing_c = sum of y[i,c]
            mixing_c = solver.Sum([y[(i, c)] for i in range(N)])
            # combine them
            objective_terms.append(alpha * underfill_c + beta * mixing_c)

        total_objective_expr = solver.Sum(objective_terms)
        solver.Minimize(total_objective_expr)

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Objective function configured ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Solving...')
        print(colored("\n[5/5] Solving the optimization problem...", 'cyan'))
        
        # 6) Solve
        status = solver.Solve()
        if status not in (solver.OPTIMAL, solver.FEASIBLE):
            raise Exception("No feasible solution found by the solver.")

        elapsed = time.time() - start_time
        print(colored(f"     ✓ Solution found ({elapsed:.2f}s)", 'green'))
        
        update_spinner('Extracting solution...')
        
        # 7) Extract solution
        solver_contingents = []
        for c in range(max_contingents):
            assigned_sum = sum(int(x[(i, c)].solution_value()) for i in range(N))
            if assigned_sum == 0:
                continue  # skip empty
            cont_dict = {}
            for i in range(N):
                val = int(x[(i, c)].solution_value())
                if val > 0:
                    cont_dict[groups[i]] = val
            solver_contingents.append(cont_dict)

        # Combine pre-allocated contingents with solver's results
        all_contingents = pre_allocated_contingents + solver_contingents

        total_elapsed = time.time() - start_time
        spinner.succeed(colored(f'Optimization completed in {total_elapsed:.2f} seconds', 'green'))
        
        return all_contingents, solver.Objective().Value()

    except Exception as e:
        spinner.fail(colored(f'Error during optimization: {str(e)}', 'red'))
        raise e

def main():
    print(colored("\n=== Parade Allocation Optimizer ===", 'yellow', attrs=['bold']))
    
    # Load configuration
    config = load_config()
    
    # Extract values from config
    contingent_row_size = config["contingent_row_size"]
    capacity = config["capacity"]
    strict_min_capacity = config["strict_min_capacity"]
    group_sizes = config["group_sizes"]
    alpha = config["alpha"]
    beta = config["beta"]
    fix_num_contingents = config["fix_num_contingents"]
    time_limit = config["time_limit"]

    total_people = sum(info["size"] for info in group_sizes.values())
    
    try:
        contingents, obj_val = allocate_contingents(
            group_sizes=group_sizes,
            capacity=capacity,
            strict_min_capacity=strict_min_capacity,
            contingent_row_size=contingent_row_size,
            alpha=alpha,
            beta=beta,
            use_all=True,
            fix_num_contingents=fix_num_contingents,
            time_limit=time_limit
        )
    except Exception as e:
        print(colored(f'Optimization failed: {str(e)}', 'red'))
        return

    print(colored("\n=== Results ===", 'yellow', attrs=['bold']))
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
        # print(f"\nFormation:\n{create_contingent_ascii(total_in_cont, contingent_row_size)}\n")
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
        
        # Write input parameters
        writer.writerow(['Input Parameters'])
        writer.writerow(['Parameter', 'Value'])
        writer.writerow(['Contingent Row Size', contingent_row_size])
        writer.writerow(['Contingent Capacity', capacity])
        writer.writerow(['Strict Minimum Capacity', strict_min_capacity])
        writer.writerow(['Alpha (underfill penalty)', alpha])
        writer.writerow(['Beta (mixing penalty)', beta])
        writer.writerow(['Fixed Number of Contingents', fix_num_contingents])
        writer.writerow(['Solver Time Limit (seconds)', time_limit])
        writer.writerow([])
        
        # Write group sizes
        writer.writerow(['Input Group Sizes'])
        writer.writerow(['Group', 'Size', 'Avoid Split'])
        for group, info in group_sizes.items():
            writer.writerow([group, info['size'], info['avoid_split']])
        writer.writerow([])
        
        # Write results summary
        writer.writerow(['Results Summary'])
        writer.writerow(['Total People', total_people])
        writer.writerow(['Objective Value', f"{obj_val:.2f}"])
        writer.writerow([])
        
        # Write contingent details header
        writer.writerow(['Contingent Details'])
        writer.writerow(['Contingent #', 'Total People', 'Group Assignments', 'Number of Groups'])
        
        # Write each contingent's details
        for idx, cont in enumerate(contingents, start=1):
            total_in_cont = sum(cont.values())
            letters_used = len(cont)
            groups_list = ", ".join(f"{g}:{n}" for g, n in cont.items())
            writer.writerow([idx, total_in_cont, groups_list, letters_used])
        
        # Write summary statistics
        writer.writerow([])
        writer.writerow(['Summary Statistics'])
        writer.writerow(['Total Contingents Used', len(contingents)])
        writer.writerow(['Total People Assigned', grand_total_assigned])
        writer.writerow(['All Members Assigned', 'Yes' if True else 'No'])

    print("\nResults have been saved to:", csv_filename)

if __name__ == "__main__":
    main()
