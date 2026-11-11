"""Run the PS-052 command-file pipeline and generate all CSV reports."""
from pathlib import Path
from src.compliance_engine import ComplianceEngine

ROOT = Path(__file__).resolve().parent
engine = ComplianceEngine(data_dir=str(ROOT / "sample_data"))
engine.execute_command_file(str(ROOT / "sample_data" / "commands.txt"))

print("\nPS-052 pipeline completed successfully.")
print(f"Shipments loaded: {len(engine.shipments)}")
print(f"Consignment decisions: {len(engine.output_decisions)}")
print(f"Excursion/data-gap records: {len(engine.output_excursions)}")
print(f"Carrier penalty records: {len(engine.output_penalties)}")
print(f"Claim allocation records: {len(engine.output_claims)}")
print(f"Release certificates: {len(engine.output_certificates)}")
print(f"Reports saved in: {ROOT / 'output'}")
