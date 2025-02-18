import sys
import os
import subprocess
import itertools
import re
import time

def copy_xsb_to_output(input_file, output_dir):
    """
    Copies the input XSB board to the output directory.
    

    Args:
        input_file (str): path to input .xsb file 
        output_dir (str): path to the output directory
    """
    output_xsb_file = os.path.join(output_dir, os.path.basename(input_file))
    with open(input_file, 'r') as f_in, open(output_xsb_file, 'w') as f_out:
        f_out.write(f_in.read())
    print(f"\nCopied input XSB board to: {output_xsb_file}")


def comment_out_illegal_two_brackets(strings, range1, range2 = []):
    """
    Processes a list of strings where each string contains multiple lines of SMV text.
    Evaluates pairs of bracketed expressions ([phrase1][phrase2]) if at least one contains a "+".
    Comments out lines with out-of-range or invalid values.

    Args:
        strings (list of str): List of strings, each containing SMV lines separated by `\n`.
        range1 (tuple): Allowed range for the first bracket expression (min1, max1), last value included.
        range2 (tuple): Allowed range for the second bracket expression (min2, max2), last value included.

    Returns:
        list of str: List of processed strings with lines commented or updated as needed.
    """
    processed_strings = []

    for smv_text in strings:
        # Split the string into individual lines
        lines = smv_text.split('\n')
        processed_lines = []

        for line in lines:
            match = re.match(r'(\s*)(\S.*)', line)
            if match:
                leading_spaces, line = match.groups()

            matches = re.findall(r'\[(.*?)\]', line)
            if not matches:
                # Skip the line if no brackets are found
                processed_lines.append(leading_spaces+line)
                continue

            is_illegal = False
            evaluated_terms = []

            for phrase in matches:
                try:
                    # Evaluate the expression inside the brackets
                    value = eval(phrase)

                    # Determine the range to check
                    if len(evaluated_terms) % 2 == 0:  # Alternate between range1 and range2
                        in_range = range1[0] <= value <= range1[1]
                    else:
                        in_range = range2[0] <= value <= range2[1]

                    # # Determine the range to check
                    # in_range = range1[0] <= value <= range1[1]

                    if not in_range:
                        is_illegal = True

                    # Replace original phrase with evaluated value
                    evaluated_terms.append(f"[{value}]")
                except Exception:
                    # If evaluation fails, consider the line illegal
                    is_illegal = True
                    evaluated_terms.append("[ERROR]")

            # Reconstruct the line with evaluated terms
            for original, replacement in zip(matches, evaluated_terms):
                line = line.replace(f"[{original}]", replacement, 1)

            # Comment out the line if it's illegal
            if is_illegal:
                line = f"-- {line}"

            # Add the processed line to the list
            processed_lines.append(leading_spaces+line)

        # Reassemble the processed lines into a string
        processed_strings.append('\n'.join(processed_lines))    

    return processed_strings


def expand_macro(macro_template, *params):
    """expand the given macro template multiple times, each time for one element of the iterables in params

    Args:
        macro_template (str): the macro to expand
        params: tuples of (placeholder, an iterable of values for this placeholder)

    Returns:
        list: list of strings of the expanded macro with substituted values 

    Example: A call to the function can be like - expand_macros(("row",a),("col",b),("name",c))
            where, for instance, a=[1], b=range(2,4), c=[4,5,6]
    """
    expanded_macros = []
    
    placeholders = [tuple[0] for tuple in params]
    values = [tuple[1] for tuple in params]
    
    for combination in itertools.product(*values):
        new_macro = "" + macro_template
        for i,placeholder in enumerate(placeholders):
            new_macro = new_macro.replace(placeholder, str(combination[i]))
        expanded_macros.append(f"{new_macro}")
    
    return expanded_macros


def analyze_xsb_file(xsb_file_path):
    """
    Analyzes the .xsb file to determine the board dimensions and converts the board into a list of lists.
    
    Args:
        file_path (str): The path to the .xsb file.
    
    Returns:
        board (list of list of str): The Sokoban board as a list of lists.
    """
    with open(xsb_file_path, 'r') as f:
        lines = [line.strip() for line in f.readlines()]

    # Convert the board to a list of lists
    board = [list(line) for line in lines]

    return board


def generate_nuxmv_file(input_board, smv_file):
    """
    Generates a nuXmv file based on the input Sokoban board.
    
    Args:
        input_board (list of str): The Sokoban board as a list of strings.
        smv_file (str): The name of the .smv file to generate.
    """

    rows = len(input_board)
    cols = 0 if rows == 0 else len(input_board[0])

   
    # handle macro - VAR and beginning of DEFINE
    with open("./macros/macro_1_VAR_DEFINE.txt", "r") as infile:
        macro_template = infile.read()
    expanded_macros = expand_macro(macro_template,("MAX_ROW_MINUS_ONE",[rows-2]),("MAX_COL_MINUS_ONE",[cols-2]))

    with open(smv_file, 'w') as f:
        for macro in expanded_macros:
            f.write(f"{macro}\n\n")
    

    # handle macro - targets_occupied, victory assertion and init(direction)
    targets = [(i,j) for i,line in enumerate(input_board) for j,char in enumerate(line) if char in [".","*","+"]]
    occupied_str = ""
    for i,target in enumerate(targets):
        occupied_str += f"\t\tis_target_{i+1}_occupied := board[{target[0]}][{target[1]}] = box;\n"    

    victory_def = "\n\t\tvictory := " + " & ".join([f"is_target_{i}_occupied" for i in range(1,len(targets)+1)]) + ";"
    

    with open(smv_file, 'a') as f:
        f.write(f"{occupied_str}\n")
        f.write(f"\n{victory_def}\n\n")
        f.write("\tASSIGN\n\n\t\tinit(direction) := stay;\n\n")


    # handle macro - init(board[][])
    symbols = {
        "@" : "man",
        "+" : "man",
        "$" : "box",
        "*" : "box",
        "#" : "wall",
        "-" : "vacant",
        "." : "vacant"
    }
    init_board = ""
    for i,line in enumerate(input_board):
        if i == 0 or i == rows-1:
            continue
        for j,char in enumerate(line):
            if j == 0 or j == cols-1:
                continue
            init_board += f"\t\tinit(board[{i}][{j}]) := {symbols[char]};\n" 
        init_board += "\n"
      
    with open(smv_file, 'a') as f:
        f.write(init_board + "\n\n")
        f.write("\t\tnext(direction) := {up, down, right, left};\n\n")

    
    # Expand the macro for all ROW and COL combinations
    
    row_range = range(1,rows-1)
    col_range = range(1,cols-1)

    range1 = (1,rows-2)
    range2 = (1,cols-2)
    
    # Read the input file
    with open("./macros/macro_3_next_board.txt", "r") as infile:
        macro_template = infile.read()

    expanded_macros = expand_macro(macro_template, ("ROW",row_range), ("COL",col_range))
    expanded_macros = comment_out_illegal_two_brackets(expanded_macros, range1, range2)
    
    # Write the expanded macros to the output file
    with open(smv_file, "a") as f:
        f.write("\n\n".join(expanded_macros))


    # Write the specification for victory
    with open(smv_file, "a") as f:
        f.write("\n\nCTLSPEC NAME ctl_not_victory := AG !victory\n")
        f.write("LTLSPEC NAME ltl_not_victory := G !victory")


    print(f"Generated nuXmv file at: {smv_file}")


def run_nuxmv(smv_file, output_file, commands):
    """
    Executes nuXmv on the given .smv file and saves the output.
    
    Args:
        smv_file (str): The path to the .smv file.
        output_file (str): The path to the file where nuXmv output will be written.
        commands (str): A string of series of commands (separated by newline to the nuXmv program)
    
    Returns:
        tuple: (a,b), where 'a' is the execution stdout and 'b' is execution time.
    """
    
    start_time = time.time()  # Start timing
    
    try:
        # Run nuXmv interactively
        process = subprocess.Popen(
            ["nuXmv", "-int", smv_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Send commands and get output
        stdout, stderr = process.communicate(commands)

        end_time = time.time()  # End timing
        execution_time = end_time - start_time

        # result = subprocess.run(
        #     ["nuXmv", smv_file],
        #     capture_output=True,
        #     text=True,
        #     check=True
        # )

        # with open(output_file, 'w') as f:
        #     f.write(result.stdout)
        # print(f"nuXmv output saved to: {output_file}")
        # return (result.stdout, execution_time)

        with open(output_file, 'w') as log_file:
            log_file.write(stdout)
            if stderr:
                log_file.write("\nErrors:\n" + stderr)
        
        return stdout, execution_time

    

    except subprocess.CalledProcessError as e:
        print(f"Error executing nuXmv: {e.stderr}")
        sys.exit(1)


def parse_nuxmv_output(nuxmv_output: str, k_steps = 40) -> str:
    """
    Converts nuXmv output into LURD format, or returns 'There is no solution' if unsolvable.
    
    Args:
        nuxmv_output (str): The output of the nuXmv command.
        k_steps (int, optional): The bound of steps in BMC (SAT), required for parsing a "no solution" option in SAT output

    Returns:
        str: The solution in LURD format, or "There is no solution".
    """

    # Check if the board is unsolvable
    if "-- specification AG !victory  is true" in nuxmv_output:
        result = "There is no solution."
    elif nuxmv_output.endswith(f"-- no counterexample found with bound {k_steps}\nnuXmv > "):
        return "There is no solution." 
    else:
        # Mapping of directions to LURD/lurd format
        direction_map = {
            "up": "U",
            "down": "D",
            "left": "L",
            "right": "R",
        }

        # Split the output into separate states using "-> State: X.Y <-" as a delimiter
        state_splits = re.split(r"\n\s*-> State: \d+\.\d+ <-\s*\n", nuxmv_output)[1:]

        lurds = []
        previous_direction = None  # Track the last known direction

        for state in state_splits:
            lines = state.strip().split("\n")
            # Extract direction
            direction = None
            for line in lines:
                if line.strip().startswith("direction = "):
                    direction = line.split("= ")[1].strip()
                    break

            # If no direction is found, assume the previous direction
            if direction is None:
                direction = previous_direction
            else:
                previous_direction = direction  # Update last known direction
            
            if direction is None:
                continue  # Skip state if we still don't have any direction

            
            # Determine if a box was pushed
            pushed = False
            for line in lines:
                if line.endswith("box"):
                    pushed = True
                    break

            # Append the appropriate LURD/lurd character
            if direction in direction_map:
                lurds.append(direction_map[direction].upper() if pushed else direction_map[direction].lower())

        result = "".join(lurds)

    return result



def main():

    #####################################
    ### Check inputs and handle files ###
    #####################################

    # Check that the correct number of arguments is provided
    if len(sys.argv) != 3:
        print("Usage: python file_name.py <input board> <output directory>")
        sys.exit(1)

    # Parse command-line arguments
    input_file = sys.argv[1]
    output_dir = sys.argv[2]

    # Ensure the input file exists
    if not os.path.isfile(input_file):
        print(f"Error: The input file '{input_file}' does not exist.")
        sys.exit(1)

    # Ensure the output directory exists
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
        print(f"The output directory '{output_dir}' was not exist; A new directory created")

    # remove old .xsb files
    for f in os.listdir(output_dir):
        if re.search(r'^.*\.xsb$', f): # Matches any string ending with ".xsb"
            os.remove(os.path.join(output_dir, f))

    # Copy the input XSB board to the output directory
    copy_xsb_to_output(input_file, output_dir)




    ############################################
    ### Analyze .xsb file and generate model ###
    ############################################

    # Generate the .smv file
    board = analyze_xsb_file(input_file)
    smv_file = os.path.join(output_dir, "model.smv")
    generate_nuxmv_file(board, smv_file)




    ####################################
    ### Run nuXmv and get the output ###
    ####################################
    
    # Run with BDD engine
    nuxmv_output_file = os.path.join(output_dir, "nuxmv_output_BDD.txt")
    nuxmv_output_BDD, exec_time_BDD = run_nuxmv(smv_file, nuxmv_output_file, f"go\ncheck_ctlspec -P ctl_not_victory\nquit")
    print(f"\nExecution (BDD) completed in {exec_time_BDD:.6f} seconds")

    # Run with SAT engine
    nuxmv_output_file = os.path.join(output_dir, "nuxmv_output_SAT.txt")
    k_steps = 40
    nuxmv_output_SAT, exec_time_SAT = run_nuxmv(smv_file, nuxmv_output_file, f"go_bmc\ncheck_ltlspec_bmc -P ltl_not_victory -k {k_steps}\nquit")
    print(f"Execution (SAT) completed in {exec_time_SAT:.6f} seconds\n")


    # Parse the solution from nuXmv output
    solution_BDD = parse_nuxmv_output(nuxmv_output_BDD)
    solution_SAT = parse_nuxmv_output(nuxmv_output_SAT, k_steps)

    # Write the solution to a text file
    solution_file = os.path.join(output_dir, "solution_BDD.txt")
    with open(solution_file, 'w') as f:
        f.write(solution_BDD)
        f.write(f"\nExecution completed in {exec_time_BDD:.6f} seconds")
    print(f"Solution (BDD) written to: {solution_file}")

    solution_file = os.path.join(output_dir, "solution_SAT.txt")
    with open(solution_file, 'w') as f:
        f.write(solution_SAT)
        f.write(f"\nExecution completed in {exec_time_SAT:.6f} seconds")
    print(f"Solution (SAT) written to: {solution_file}")

if __name__ == "__main__":
    main()
