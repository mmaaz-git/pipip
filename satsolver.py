import argparse
from zipfile import ZipFile
from pathlib import Path
import tempfile
import sys
import subprocess

WHEEL_METADATA = """
Wheel-Version: 1.0
Generator: sat-solver (1.0.0)
Root-Is-Purelib: true
Tag: py3-none-any
""".strip()

def create_variable_package(package_dir: Path, var: int, version: float):
    """Create a wheel file for a variable package."""
    name = f"x{var}"
    filename = f"{name}-{version}-py3-none-any.whl"

    with ZipFile(package_dir.joinpath(filename), "w") as writer:
        metadata = [
            f"Name: {name}",
            f"Version: {version}",
            "Metadata-Version: 2.2"
        ]

        # Write the metadata files
        writer.writestr(f"{name}-{version}.dist-info/METADATA", "\n".join(metadata))
        writer.writestr(f"{name}-{version}.dist-info/WHEEL", WHEEL_METADATA)
        writer.writestr(f"{name}-{version}.dist-info/RECORD", "")

def create_clause_package(package_dir: Path, clause_num: int, version: int, dependencies: list):
    """Create a wheel file for a clause package with dependencies."""
    name = f"c{clause_num}"
    filename = f"{name}-{version}.0-py3-none-any.whl"

    with ZipFile(package_dir.joinpath(filename), "w") as writer:
        metadata = [
            f"Name: {name}",
            f"Version: {version}.0",
            "Metadata-Version: 2.2"
        ]

        # Add dependencies
        for dep in dependencies:
            metadata.append(f"Requires-Dist: {dep}")

        writer.writestr(f"{name}-{version}.0.dist-info/METADATA", "\n".join(metadata))
        writer.writestr(f"{name}-{version}.0.dist-info/WHEEL", WHEEL_METADATA)
        writer.writestr(f"{name}-{version}.0.dist-info/RECORD", "")

def generate_requirements(num_vars: int, clauses: list) -> str:
    """Generate requirements.in content"""
    lines = []

    # Variable packages must be either 1.0 or 2.0
    for i in range(1, num_vars + 1):
        lines.append(f'x{i}>=1.0,<=2.0')

    # Each clause must be satisfied with one of its versions
    for i, clause in enumerate(clauses, 1):
        lines.append(f'c{i}>=1.0,<={len(clause)}.0')

    return '\n'.join(lines)

def generate_packages(num_vars: int, clauses: list, package_dir: Path):
    """Generate all necessary wheel packages."""
    package_dir.mkdir(exist_ok=True, parents=True)

    # Create variable packages (version 1.0 for False, 2.0 for True)
    for var in range(1, num_vars + 1):
        create_variable_package(package_dir, var, 1.0)
        create_variable_package(package_dir, var, 2.0)

    # Create clause packages
    for i, clause in enumerate(clauses, 1):
        for version, lit in enumerate(clause, 1):
            var = abs(lit)
            required_version = "2.0" if lit > 0 else "1.0"
            dependencies = [f"x{var}=={required_version}"]
            create_clause_package(package_dir, i, version, dependencies)

def parse_dimacs(dimacs_str: str):
    """Parse DIMACS CNF format into num_vars and clauses."""
    num_vars = 0
    clauses = []

    for line in dimacs_str.split('\n'):
        # Skip empty lines, comments, problem line
        line = line.strip()
        if not line or line.startswith('c') or line.startswith('p') or line.startswith('%'):
            continue

        # Parse numbers until 0 or % and add as clause
        nums = [int(x) for x in line.split() if x != '0' and x != '%']
        if nums:  # only add if we got some numbers
            clauses.append(nums)

    # If num_vars wasn't specified in a 'p' line, calculate it from the clauses
    if num_vars == 0:
        num_vars = max(abs(lit) for clause in clauses for lit in clause)

    return num_vars, clauses

def parse_solution(requirements_txt: Path) -> dict[int, bool]:
    """Parse the requirements.txt to get variable assignments.
    Returns a dict mapping variable number to boolean value (True if 2.0, False if 1.0)"""
    assignments = {}

    try:
        with open(requirements_txt) as f:
            for line in f:
                # Look for lines like "x1==2.0"
                if line.startswith('x'):
                    var_str, version = line.strip().split('==')
                    var_num = int(var_str[1:])  # Extract number from 'x1'
                    assignments[var_num] = (version == "2.0")
    except FileNotFoundError:
        return None  # No solution found

    return assignments

def solve_sat(dimacs_str: str, use_uv: bool = False) -> bool:
    """Try to solve the SAT problem using pip-compile."""
    num_vars, clauses = parse_dimacs(dimacs_str)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        package_dir = tmpdir_path / "packages"

        # Generate all necessary wheel files
        generate_packages(num_vars, clauses, package_dir)

        # Create requirements.in
        requirements_in = tmpdir_path / "requirements.in"
        requirements_txt = tmpdir_path / "requirements.txt"

        with open(requirements_in, 'w') as f:
            f.write(generate_requirements(num_vars, clauses))

        # Choose compiler command based on use_uv flag
        compiler_cmd = ['uv', 'pip', 'compile'] if use_uv else ['pip-compile']

        # Try to resolve dependencies
        result = subprocess.run(
        [
            *compiler_cmd,  # Unpacks either ['uv', 'pip', 'compile'] or ['pip-compile']
            '--find-links', str(package_dir),
            '--no-annotate',
            '--no-header',
            str(requirements_in),
            '-o', str(requirements_txt)
        ],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            assignments = parse_solution(requirements_txt)
            return True, assignments
        else:
            return False, None


def main():
    parser = argparse.ArgumentParser(
        description='Solve SAT problems using pip as the solver',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example DIMACS CNF format:
c This is a comment
p cnf 4 3
1 2 -3 0
1 3 4 0
-2 3 4 0
        """)

    parser.add_argument('input_file',
                       type=argparse.FileType('r'),
                       help='Path to DIMACS CNF file')
    parser.add_argument('--uv', action='store_true', help='Use uv instead of pip-compile')

    args = parser.parse_args()

    try:
        dimacs = args.input_file.read()
        is_satisfiable, assignments = solve_sat(dimacs, use_uv=args.uv)

        if is_satisfiable:
            print("SATISFIABLE")
            if assignments:
                for var, value in sorted(assignments.items()):
                    print(f"x{var} = {value}")
        else:
            print("UNSATISFIABLE")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        args.input_file.close()

if __name__ == "__main__":
    main()
