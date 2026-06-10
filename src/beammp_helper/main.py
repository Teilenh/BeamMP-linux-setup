import sys
import time
from rich.console import Console

from beammp_helper.core.config import STATE_FILE, load_state, save_state
from beammp_helper.core.detector import detect_beamng_game_path, detect_distro, detect_steam_type
from beammp_helper.core.integration import generate_desktop_entries, generate_wrapper
from beammp_helper.tui.menu import get_key, run_installation_flow, run_path_selection, run_tui


def run_first_run_wizard() -> None:
	"""
	Interactive first-run setup flow.

	Covers: distro detection → Steam detection → BeamNG path detection →
	optional BeamMP installation → optional desktop integration.

	Returns after setup is complete; the caller is responsible for launching
	the TUI afterwards.
	"""
	console = Console()
	console.clear()
	console.print("[bold magenta]Welcome to BeamMP-Helper![/bold magenta]\n")
	console.print("This wizard will configure everything you need to run BeamMP on Linux.\n")

	state = load_state()
	state["last_check_timestamp"] = int(time.time())

	# --- Distro & package manager detection ---
	distro_id, distro_family, package_manager = detect_distro()
	state["distro_id"] = distro_id
	state["distro_family"] = distro_family
	state["package_manager"] = package_manager
	save_state(state)

	if distro_id:
		console.print(
			f"[bold green]Detected distro:[/bold green] {distro_id} "
			f"(family: {distro_family}, package manager: {package_manager})\n"
		)
	else:
		console.print("[bold yellow]Could not detect distro from /etc/os-release.[/bold yellow]\n")

	# --- Steam type detection ---
	steam_type, steam_path = detect_steam_type()
	state["steam_type"] = steam_type
	save_state(state)

	if steam_type != "none":
		console.print(f"[bold green]Detected Steam:[/bold green] {steam_type} at {steam_path}\n")
	else:
		console.print("[bold yellow]Steam not detected — BeamNG path will need to be set manually.[/bold yellow]\n")

	# --- BeamNG game path detection ---
	detected_path = detect_beamng_game_path()
	if detected_path:
		state["beamng_path"] = str(detected_path)
		save_state(state)
		console.print(f"[bold green]Auto-detected BeamNG.drive path:[/bold green] {detected_path}\n")
	else:
		console.print("[bold yellow]Could not auto-detect BeamNG.drive installation path.[/bold yellow]")
		console.print("Please set the path now.\n")
		run_path_selection(console)
		state = load_state()

	# --- Optional BeamMP installation ---
	if not state.get("beammp_binary_path"):
		console.print("\nBeamMP launcher is not installed.")
		console.print("Would you like to install/compile BeamMP now? (y/n): ", end="")
		if input().strip().lower() == "y":
			run_installation_flow(console)
			state = load_state()
		else:
			console.print("\nSkipping installation. You can install it later from the main menu.")
			console.print("Press any key to continue...")
			get_key()
			return

	# --- Optional desktop integration ---
	if state.get("beammp_binary_path"):
		console.print("\nWould you like to create desktop entries for BeamMP and BeamMP-Helper? (y/n): ", end="")
		if input().strip().lower() == "y":
			if generate_wrapper(state):
				state = load_state()
				if generate_desktop_entries(state):
					console.print(
						"[bold green]Desktop integration installed successfully![/bold green]"
					)
					console.print(
						f"  Wrapper: ~/.local/bin/BeamMP-Helper\n"
						f"  Entries: ~/.local/share/applications/"
					)
				else:
					console.print("[bold red]Failed to write desktop entries.[/bold red]")
			else:
				console.print("[bold red]Failed to generate wrapper script.[/bold red]")
		else:
			console.print("Skipping desktop integration. Run from the menu later if needed.")

	console.print("\nSetup complete! Opening the main menu...\n")
	console.print("Press any key to continue...")
	get_key()


def main() -> None:
	state = load_state()
	args = sys.argv[1:]
	is_tui_mode = not args or args[0] == "tui"

	# Trigger the wizard if this looks like a first run:
	# state file missing, or the file exists but critical fields were never set.
	needs_wizard = not STATE_FILE.exists() or not state.get("beamng_path")

	if needs_wizard and is_tui_mode:
		run_first_run_wizard()
		run_tui()
		return

	# All other invocations (CLI commands, or normal TUI after setup) go through
	# the standard argument dispatcher.
	from beammp_helper.cli.parser import parse_and_run
	parse_and_run(args)


if __name__ == "__main__":
	main()
