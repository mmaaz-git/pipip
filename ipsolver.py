from satsolver import solve_sat
import argparse
import sys

def encode_ilp_to_sat(A, b):
    """
    Encodes a system of ILP constraints Ax <= b where:
    - A is a matrix of coefficients (list of lists)
    - b is a vector of bounds (list)
    - All variables are binary
    - b[i] >= 0 for all i

    Returns a list of clauses in CNF form.
    Variable numbering:
    1 to n: original x_i variables
    n+1 to 2n: corresponding z_i variables (complements)
    Rest: s_ij variables for each constraint
    """
    if not A or not A[0]:
        return []

    num_constraints = len(A)
    num_vars = len(A[0])
    clauses = []

    # First, add clauses for complementary variables
    # For each x_i (variable i), add z_i (variable i + num_vars)
    # Ensure x_i = ¬z_i with clauses: (¬x_i ∨ ¬z_i) ∧ (x_i ∨ z_i)
    for i in range(num_vars):
        x_i = i + 1
        z_i = x_i + num_vars
        clauses.append([-x_i, -z_i])  # can't both be true
        clauses.append([x_i, z_i])    # can't both be false

    # Base index for s_ij variables starts after all x_i and z_i variables
    base_s_idx = 2 * num_vars + 1

    def get_s_idx(constraint_num, i, j):
        """Get variable number for s_ij in the given constraint"""
        # For each constraint, we need (num_vars + 1) * (max_sum + 1) s_ij variables
        max_sum = sum(abs(coef) for coef in A[constraint_num])
        offset = constraint_num * (num_vars + 1) * (max_sum + 1)
        return base_s_idx + offset + i * (max_sum + 1) + j

    # Handle each constraint separately
    for constraint_num in range(num_constraints):
        coeffs = A[constraint_num]
        bound = b[constraint_num]

        # First check if bound is negative, then flip it
        # This might create negative coefficients so flip it before handling negatives
        geq = False
        if bound < 0:
            bound = -bound
            coeffs = [-c for c in coeffs]
            geq = True

        # Now handle negative coefficients
        for i, coeff in enumerate(coeffs):
            if coeff < 0:
                bound += abs(coeff) # adjust the bound
                coeffs[i] = abs(coeff)

        max_sum = sum(abs(coef) for coef in coeffs)

        # Base cases for i=0
        clauses.append([get_s_idx(constraint_num, 0, 0)])  # s_00 = true
        for j in range(1, max_sum + 1):
            clauses.append([-get_s_idx(constraint_num, 0, j)])  # s_0j = false

        # Generate clauses for each variable in this constraint
        for i in range(1, num_vars + 1):
            w_i = abs(coeffs[i-1])  # Use absolute value of coefficient
            # Choose x_i or z_i based on coefficient sign
            var_i = i if coeffs[i-1] >= 0 else (i + num_vars)

            for j in range(max_sum + 1):
                s_ij = get_s_idx(constraint_num, i, j)
                s_prev_j = get_s_idx(constraint_num, i-1, j)

                if w_i > j:
                    # Case 1: weight too large, can't include this variable
                    clauses.append([-s_ij, s_prev_j])
                    clauses.append([-s_ij, -var_i])
                    clauses.append([-s_prev_j, var_i, s_ij])
                else:
                    # Case 2: can choose to include this variable or not
                    s_prev_j_minus_w = get_s_idx(constraint_num, i-1, j - w_i)
                    clauses.append([-s_ij, s_prev_j, s_prev_j_minus_w])
                    clauses.append([-s_ij, s_prev_j, var_i])
                    clauses.append([-s_ij, -var_i, s_prev_j_minus_w])
                    clauses.append([-s_prev_j, var_i, s_ij])
                    clauses.append([-s_prev_j_minus_w, -var_i, s_ij])

        # Add bounding constraint:
        if not geq:
            # need sum <= bound, so introduce ¬s_nk for k > bound (multiple clauses)
            for k in range(bound + 1, max_sum + 1):
                clauses.append([-get_s_idx(constraint_num, num_vars, k)])
        else:  # geq case
            if bound > max_sum:
                # this case is always infeasible
                # so just make it UNSAT via p AND ¬p
                clauses.append([1])
                clauses.append([-1])
            else:
                # need sum >= bound, so at least one of s_nk for k >= bound must be true (one clause)
                at_least_one = [get_s_idx(constraint_num, num_vars, k)
                                for k in range(bound, max_sum + 1)]
                clauses.append(at_least_one)

    return clauses

def clauses_to_dimacs(clauses, num_vars) -> str:
    """Convert clauses to DIMACS CNF format string."""
    lines = []

    # Add header
    lines.append(f"p cnf {num_vars} {len(clauses)}")

    # Add clauses
    for clause in clauses:
        # Each clause needs to end with 0
        clause_str = " ".join(str(lit) for lit in clause) + " 0"
        lines.append(clause_str)

    return "\n".join(lines)

def decode_solution(solution, num_vars):
    """
    Takes a list of positive and negative integers representing a SAT solution
    and returns the values of the original variables.
    """
    return {f"x{i+1}": 1 if solution.get(i+1, False) else 0
            for i in range(num_vars)}

def solve_ilp(A, b, use_uv: bool = False):
    """
    Solves a binary ILP system Ax <= b using SAT encoding.
    Returns (is_satisfiable, solution_dict) where solution_dict maps variable names to 0/1 values.
    """

    # Get the CNF clauses
    clauses = encode_ilp_to_sat(A, b)

    # Calculate number of variables
    num_vars = max(abs(lit) for clause in clauses for lit in clause)

    # Convert to DIMACS format
    dimacs_str = clauses_to_dimacs(clauses, num_vars)

    # Solve using pipip
    is_sat, solution = solve_sat(dimacs_str, use_uv=use_uv)

    if not is_sat:
        return False, None

    # Extract only the original variables from the solution
    return True, decode_solution(solution, len(A[0]))

def save_dimacs_cnf(filename: str, dimacs_str: str):
    """Saves a DIMACS CNF string to a file."""
    with open(filename, 'w') as f:
        f.write(dimacs_str)

def parse_ilp_file(filename):
    """Parse matrix A and vector b from file.
    Each line: a1 a2 ... an b
    where a1..an are coefficients and b is the bound.
    Lines starting with 'c' are ignored as comments."""
    A = []
    b = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('c'):  # skip empty lines and comments
                nums = list(map(int, line.split()))
                A.append(nums[:-1])  # all but last number are coefficients
                b.append(nums[-1])   # last number is bound
    return A, b

def main():
    parser = argparse.ArgumentParser(description='Binary ILP solver using SAT encoding')
    parser.add_argument('input', help='Input ILP file')
    parser.add_argument('--uv', action='store_true', help='Use uv instead of pip-compile')

    args = parser.parse_args()

    try:
        A, b = parse_ilp_file(args.input)
        is_feasible, solution = solve_ilp(A, b, use_uv=args.uv)  # Pass the flag

        if is_feasible:
            print("Feasible")
            print(solution)
        else:
            print("Infeasible")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()





