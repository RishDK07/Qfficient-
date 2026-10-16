"""
Convenient entry point for running Thermodynamic QUBO Grid optimizations from the project root.
Usage:
    python run.py -n 60
    python run.py -n 40 --solar 4 --ev 2
    python run.py --sweep
"""

from thermodynamic_grid_qubo.cli import main

if __name__ == "__main__":
    main()
