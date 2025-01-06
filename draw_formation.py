import csv
import math
import csv

def create_contingent_ascii(total_people, row_size=5):
    columns = math.ceil(total_people / row_size)

    total_grid_size = row_size * columns
    missing = total_grid_size - total_people
    
    seats = [[True for _ in range(columns)] for _ in range(row_size)]
    
    if missing > 0:
        col_to_remove = 1
        seats_removed = 0
        
        while seats_removed < missing and col_to_remove < columns:
            # go from bottom row=4 (index=4) up to top row=0
            for row in range(row_size-1, -1, -1):
                if seats_removed >= missing:
                    break  # we've removed all we need
                # remove this seat (row, col_to_remove)
                seats[row][col_to_remove] = False
                seats_removed += 1
            col_to_remove += 1
    
    result = []
    for row in range(row_size):
        row_str = []
        for col in range(columns):
            if seats[row][col]:
                row_str.append("x")
            else:
                row_str.append(" ")
        # Join them with a space
        result.append(" ".join(row_str))
    
    return "\n".join(result)

def create_parade_formation(contingents, contingent_row_size=5, capacity=90):
    contingent_displays = []
    for idx, cont in enumerate(contingents, start=1):
        total_in_cont = sum(cont.values())
        capacity_diff = abs(capacity - total_in_cont)
        
        formation = create_contingent_ascii(total_in_cont, contingent_row_size)

        composition = ", ".join(f"{n} {g}" for g, n in cont.items())
        header = f"C{idx} ({composition})"
        
        contingent_displays.append((capacity_diff, idx, header + "\n" + formation))
    
    contingent_displays.sort(key=lambda x: x[0])
    sorted_displays = [x[2] for x in contingent_displays]

    first_row_count = (len(contingents) + 1) // 2
    first_row = sorted_displays[:first_row_count]
    second_row = sorted_displays[first_row_count:]

    first_row_lines = [display.split('\n') for display in first_row]
    second_row_lines = [display.split('\n') for display in second_row]

    result = []
    
    # First row
    for line_idx in range(max(len(x) for x in first_row_lines)):
        line_parts = []
        for formation in first_row_lines:
            if line_idx < len(formation):
                line_parts.append(formation[line_idx].rjust(50))
            else:
                line_parts.append(" " * 50)

        combined_line = "".join(line_parts).lstrip()
        result.append(combined_line)
    
    result.append("")
    
    # Second row
    for line_idx in range(max(len(x) for x in second_row_lines)):
        line_parts = []
        for formation in second_row_lines:
            if line_idx < len(formation):
                line_parts.append(formation[line_idx].rjust(50))
            else:
                line_parts.append(" " * 50)

        combined_line = "".join(line_parts).lstrip()
        result.append(combined_line)

    return "\n".join(result)

def data_from_csv (csv_dir): 
    contingent_row_size = None
    capacity = None
    contingents = []

    with open(csv_dir, 'r', newline='', encoding='utf-8') as csvfile:
        all_rows = list(csv.reader(csvfile))

    all_rows = [[col.strip() for col in row] for row in all_rows]

    start_idx = -1
    for i, row in enumerate(all_rows):
        if len(row) == 1 and row[0] == "Input Parameters":
            start_idx = i
            break

    if start_idx != -1:
        idx = start_idx + 2
        while idx < len(all_rows):
            if not all_rows[idx] or len(all_rows[idx]) == 0:
                break
            if len(all_rows[idx]) == 1 and "Input Group Sizes" in all_rows[idx][0]:
                break
            
            parts = all_rows[idx]
            if len(parts) == 2:
                param_name = parts[0].strip()
                param_value = parts[1].strip()

                if param_name == "Contingent Row Size":
                    contingent_row_size = int(param_value)
                elif param_name == "Contingent Capacity":
                    capacity = int(param_value)
            idx += 1

    if contingent_row_size is None:
        contingent_row_size = 5  
    if capacity is None:
        capacity = 90  

    details_idx = -1
    for i, row in enumerate(all_rows):
        if len(row) == 1 and row[0] == "Contingent Details":
            details_idx = i
            break

    if details_idx != -1:
        idx = details_idx + 2
        while idx < len(all_rows):
            row = all_rows[idx]

            if not row or len(row) == 0:
                break
            if len(row) == 1 and "Summary Statistics" in row[0]:
                break

            # Expect 4 columns: Contingent #, Total People, Group Assignments, Number of Groups
            # e.g.: ["4", "85", "IDTI:21, SI:64", "2"]
            if len(row) == 4:
                # Group assignments can have multiple groups separated by commas,
                # e.g., "IDTI:21, SI:64"
                group_assignments_str = row[2].strip()
                
                group_dict = {}
                # Split by ',' to get each chunk like "IDTI:21" or " SI:64"
                assignments = group_assignments_str.split(",")
                for assignment in assignments:
                    assignment = assignment.strip()
                    if ":" in assignment:
                        grp_name, grp_size = assignment.split(":", 1)
                        grp_name = grp_name.strip().strip('"')
                        grp_size = grp_size.strip().strip('"')
                        group_dict[grp_name] = int(grp_size)

                contingents.append(group_dict)
            
            idx += 1

    print("Parsed contingents:", contingents)
    print("Contingent row size:", contingent_row_size)
    print("Contingent capacity:", capacity)

    return contingents, contingent_row_size, capacity

def main():
    csv_dir = "output/parade_allocation_060125_083215.csv"

    contingents, contingent_row_size, capacity = data_from_csv(csv_dir)

    # -------------------------------------------------------------------------
    # 1) Dictionary where the key is the contingent number and the value is the desired position in the final formation
    #
    positions_map = {
        1: 6, # Put contingent #1 into position 6 (top right)
        8: 5, # Put contingent #8 in position 5
        5: 4,
        3: 3,
        2: 7
    }

    # Make a new list to hold reordered contingents
    reordered_contingents = [None] * len(contingents)

    # First, place the contingents mentioned in positions_map
    for i in range(len(contingents)):
        old_pos = i + 1 
        if old_pos in positions_map:
            new_pos_index = positions_map[old_pos] - 1
            reordered_contingents[new_pos_index] = contingents[i]

    # Next, fill in the gaps for contingents not in positions_map
    fill_index = 0
    for i in range(len(contingents)):
        if reordered_contingents[i] is None:
            # Find the next old contingent that was NOT placed
            while fill_index < len(contingents):
                old_pos = fill_index + 1
                if old_pos not in positions_map:
                    reordered_contingents[i] = contingents[fill_index]
                    fill_index += 1
                    break
                fill_index += 1

    formation = create_parade_formation(reordered_contingents, contingent_row_size, capacity)

    with open('output/formation.txt', 'w', encoding='utf-8') as f:
        f.write(formation)
    
    print("\nFormation has been saved to: output/formation.txt")

if __name__ == "__main__":
    main()