import argparse
from pathlib import Path
import sys
from typing import List

from rich.console import Console

from beammp_helper.core.config import load_state, save_state

from beammp_helper.core.detector import (
	check_build_dependencies,
	get_missing_dependencies,
	validate_beamng_game_path,
)
from beammp_helper.core.installer import install_beammp
from beammp_helper.core.launcher import get_launch_preflight_error, launch_beammp
from beammp_helper.core.integration import generate_desktop_entries, generate_wrapper
from beammp_helper.core.syscheck import build_system_check_table
from beammp_helper.tui.menu import run_tui


def run_cli_install() -> None:
	console = Console()
	deps = check_build_dependencies()
	missing = get_missing_dependencies(deps)
	if missing:
		console.print("[bold red]Error: Missing build dependencies:[/bold red]")
		for item in missing:
			console.print(f" - {item}")
		sys.exit(1)

	state = load_state()
	console.print(
		"[bold green]Starting non-interactive compile/install of BeamMP...[/bold green]\n"
	)
	success = install_beammp(state, lambda line: console.print(line, end=""))
	if success:
		state = load_state()
		generate_wrapper(state)
		state = load_state()
		generate_desktop_entries(state)
		console.print(
			"\n[bold green]Installation completed and desktop entries generated![/bold green]"
		)
	else:
		console.print("\n[bold red]Installation failed.[/bold red]")
		sys.exit(1)


def run_cli_launch() -> None:
	console = Console()
	state = load_state()
	if not state.get("beamng_path") or not state.get("beammp_binary_path"):
		console.print(
			"[bold red]Error: BeamNG.drive path or BeamMP binary path not configured.[/bold red]"
		)
		console.print("Run 'BeamMP-Helper tui' or 'BeamMP-Helper set-path' first.")
		sys.exit(1)

	preflight_error = get_launch_preflight_error()
	if preflight_error:
		console.print(f"[bold red]Launch preflight failed:[/bold red] {preflight_error}")
		sys.exit(1)

	success = launch_beammp()
	if not success:
		console.print(
			"[bold red]Launch failed. Check your paths and try again.[/bold red]"
		)
		sys.exit(1)


def run_cli_check() -> None:
	console = Console()
	state = load_state()
	console.print(build_system_check_table(state))


def run_cli_set_path(path_str: str) -> None:
	console = Console()
	path = Path(path_str).expanduser().resolve()
	if not validate_beamng_game_path(path):
		console.print(
			f"[bold red]Error: '{path}' is not a valid BeamNG.drive installation directory.[/bold red]"
		)
		sys.exit(1)

	state = load_state()
	state["beamng_path"] = str(path)
	save_state(state)
	console.print(f"[bold green]Saved BeamNG.drive path to state:[/bold green] {path}")


def parse_and_run(args: List[str]) -> None:
	parser = argparse.ArgumentParser(description="BeamMP-Helper CLI")
	subparsers = parser.add_subparsers(dest="command")

	subparsers.add_parser("install", help="Compile and install BeamMP-Launcher")
	subparsers.add_parser("launch", help="Launch BeamMP directly")
	subparsers.add_parser("check", help="Run system readiness checks")

	set_path_parser = subparsers.add_parser(
		"set-path", help="Set BeamNG.drive game path"
	)
	set_path_parser.add_argument(
		"path", type=str, help="Absolute path to BeamNG.drive directory"
	)

	subparsers.add_parser("tui", help="Start the interactive terminal menu (default)")

	parsed = parser.parse_args(args)

	if parsed.command == "install":
		run_cli_install()
	elif parsed.command == "launch":
		run_cli_launch()
	elif parsed.command == "check":
		run_cli_check()
	elif parsed.command == "set-path":
		run_cli_set_path(parsed.path)
	elif parsed.command == "tui" or not parsed.command:
		run_tui()
