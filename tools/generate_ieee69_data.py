"""Generate ieee69_data.py from case69_raw.m."""
import re

with open('thermodynamic_grid_qubo/grid_engine/case69_raw.m') as f:
    text = f.read()

branch_match = re.search(r'mpc\.branch\s*=\s*\[(.*?)\];', text, re.DOTALL)
bus_match = re.search(r'mpc\.bus\s*=\s*\[(.*?)\];', text, re.DOTALL)

branches = []
for line in branch_match.group(1).strip().split('\n'):
    line = line.split('%')[0].strip().rstrip(';')
    if line:
        parts = line.split()
        branches.append((int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3])))

buses = []
for line in bus_match.group(1).strip().split('\n'):
    line = line.split('%')[0].strip().rstrip(';')
    if line:
        parts = line.split()
        buses.append((int(parts[0]), float(parts[2]), float(parts[3])))

with open('thermodynamic_grid_qubo/grid_engine/ieee69_data.py', 'w') as out:
    out.write('"""Standard IEEE 69-bus distribution feeder benchmark data.\n\n')
    out.write('Origin: M. E. Baran and F. F. Wu, Optimal capacitor placement on radial\n')
    out.write('distribution systems, IEEE Trans. Power Delivery, vol. 4, no. 1, pp. 725-734, Jan 1989.\n')
    out.write('Tie lines: D. Das, 2008 / Savic and Walters, 1989.\n"""\n\n')
    out.write('RAW_BUSES = ' + repr(buses) + '\n\n')
    out.write('RAW_BRANCHES = ' + repr(branches) + '\n\n')
    out.write('RAW_TIE_LINES = [\n')
    out.write('    (11, 43, 0.5000, 0.5000),\n')
    out.write('    (13, 21, 0.5000, 0.5000),\n')
    out.write('    (15, 46, 1.0000, 1.0000),\n')
    out.write('    (50, 59, 2.0000, 2.0000),\n')
    out.write('    (27, 65, 1.0000, 1.0000),\n')
    out.write(']\n')

print(f'Generated ieee69_data.py successfully: {len(buses)} buses, {len(branches)} branches, 5 tie lines.')
