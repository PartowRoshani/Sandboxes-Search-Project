Fitness priority patch for SandGrid Genetic Algorithm

Replace genetic_alg/fitness.py with genetic_alg/fitness.py from this archive.
Add genetic_alg/tests/test_fitness_priority.py as a new test.
No other existing files need to be changed.

Run in PowerShell from project root:
  Copy-Item .\genetic_alg\fitness.py .\genetic_alg\fitness.py.bak
  Expand-Archive -Path "$HOME\Downloads\genetic_fitness_fix.zip" -DestinationPath . -Force
  python -m unittest discover -s genetic_alg/tests -v

Note: previous benchmark CSVs were scored with the old fitness formula.
Re-run genetic experiments after this patch; keep old outputs as a separate baseline.
