"""
core/syscheck.py — Shared system readiness table builder.

Both the TUI (show_system_check) and the CLI (run_cli_check) call
build_system_check_table() so the two surfaces stay in sync automatically.
"""

from pathlib import Path

from rich.columns import Columns
from rich.console import Group
from rich.table import Table

from beammp_helper.core.config import CACHE_ROOT, DEFAULT_BEAMNG_ROOT
from beammp_helper.core.detector import (
	check_beammp_update_available,
	check_build_dependencies,
	check_hostname_resolution,
	check_vcpkg_state,
	detect_steam_type,
	get_installed_beammp_version,
	validate_beamng_game_path,
	validate_beamng_userfolder,
)


def build_system_check_table(state: dict) -> Group:
	"""
	Build and return a Rich Table summarising the full system readiness state.

	Does NOT print the table — callers are responsible for display so that both
	TUI (Console.print) and CLI contexts can use it identically.
	"""
	main_table = Table(
		title="System Readiness Check",
		show_header=True,
		header_style="bold magenta",
	)
	main_table.add_column("Component", style="cyan")
	main_table.add_column("Status", style="green")
	main_table.add_column("Details", style="yellow")

	deps_table = Table(
		title="Deps",
		show_header=True,
		header_style="bold magenta",
	)
	deps_table.add_column("Dependency", style="cyan")
	deps_table.add_column("Status", style="green")

	# --- Steam ---
	steam_type, _ = detect_steam_type()
	if steam_type != "none":
		main_table.add_row(
			"Steam Installation",
			"[bold green]OK[/bold green]",
			f"Detected {steam_type} Steam",
		)
	else:
		main_table.add_row(
			"Steam Installation", "[bold red]FAIL[/bold red]", "Steam not detected"
		)

	# --- BeamNG game path ---
	beamng_path_str = state.get("beamng_path")
	if beamng_path_str:
		path = Path(beamng_path_str)
		if validate_beamng_game_path(path):
			main_table.add_row("BeamNG Game Path", "[bold green]OK[/bold green]", str(path))
		else:
			main_table.add_row(
				"BeamNG Game Path",
				"[bold red]FAIL[/bold red]",
				f"Invalid path: {path}",
			)
	else:
		main_table.add_row(
			"BeamNG Game Path", "[bold yellow]WARN[/bold yellow]", "Not configured"
		)

	# --- BeamMP binary ---
	beammp_bin_str = state.get("beammp_binary_path")
	if beammp_bin_str:
		bin_path = Path(beammp_bin_str)
		if bin_path.exists():
			main_table.add_row(
				"BeamMP Launcher Binary",
				"[bold green]OK[/bold green]",
				str(bin_path),
			)
		else:
			main_table.add_row(
				"BeamMP Launcher Binary",
				"[bold red]FAIL[/bold red]",
				f"Binary missing: {bin_path}",
			)
	else:
		main_table.add_row(
			"BeamMP Launcher Binary", "[bold yellow]WARN[/bold yellow]", "Not installed"
		)

	# --- BeamMP update ---
	installed_version = state.get("installed_version") or None
	if not installed_version and beammp_bin_str:
		installed_version = get_installed_beammp_version(Path(beammp_bin_str))
	if not beammp_bin_str:
		main_table.add_row(
			"BeamMP Launcher Update",
			"[bold yellow]WARN[/bold yellow]",
			"Launcher not installed",
		)
	else:
		update_available, latest_version = check_beammp_update_available(installed_version)
		if latest_version is None:
			main_table.add_row(
				"BeamMP Launcher Update",
				"[bold yellow]WARN[/bold yellow]",
				"Could not reach GitHub API",
			)
		elif update_available:
			main_table.add_row(
				"BeamMP Launcher Update",
				"[bold yellow]WARN[/bold yellow]",
				f"installed={installed_version or 'unknown'}, latest={latest_version}",
			)
		else:
			main_table.add_row(
				"BeamMP Launcher Update",
				"[bold green]OK[/bold green]",
				f"installed={installed_version or 'unknown'}, latest={latest_version}",
			)

	# --- BeamNG userfolder ---
	userfolder = DEFAULT_BEAMNG_ROOT
	if validate_beamng_userfolder(userfolder):
		main_table.add_row(
			"BeamNG Userfolder & Mods",
			"[bold green]OK[/bold green]",
			str(userfolder),
		)
	else:
		main_table.add_row(
			"BeamNG Userfolder & Mods",
			"[bold red]FAIL[/bold red]",
			f"Cannot access/create: {userfolder}",
		)

	# --- Desktop integration ---
	desktop_ok = (
		Path.home() / ".local" / "share" / "applications" / "BeamMP-Helper.desktop"
	).exists()
	if desktop_ok:
		main_table.add_row(
			"Desktop Integration",
			"[bold green]OK[/bold green]",
			"Desktop entries installed",
		)
	else:
		main_table.add_row(
			"Desktop Integration",
			"[bold yellow]WARN[/bold yellow]",
			"Desktop entries missing",
		)

	# --- Build dependencies ---
	deps = check_build_dependencies()
	all_deps_ok = all(deps.values())
	if all_deps_ok:
		main_table.add_row(
			"Deps",
			"[bold green]OK[/bold green]",
			"All required tools present",
		)
	else:
		missing_names = ", ".join(dep for dep, present in deps.items() if not present)
		main_table.add_row(
			"Deps",
			"[bold red]FAIL[/bold red]",
			f"Missing: {missing_names}",
		)
	for dep, present in deps.items():
		status = "[bold green]OK[/bold green]" if present else "[bold red]MISS[/bold red]"
		deps_table.add_row(dep, status)

	# --- BeamMP backend DNS ---
	dns_ok, dns_details = check_hostname_resolution()
	main_table.add_row(
		"BeamMP Backend DNS",
		"[bold green]OK[/bold green]" if dns_ok else "[bold red]FAIL[/bold red]",
		dns_details,
	)

	# --- vcpkg ---
	vcpkg_dir = CACHE_ROOT / "vcpkg"
	vcpkg = check_vcpkg_state(vcpkg_dir)
	if vcpkg["cloned"] and vcpkg["bootstrapped"] and vcpkg["toolchain_present"]:
		main_table.add_row("vcpkg", "[bold green]OK[/bold green]", str(vcpkg_dir))
	else:
		details = []
		if not vcpkg["cloned"]:
			details.append("not cloned")
		elif not vcpkg["bootstrapped"]:
			details.append("not bootstrapped")
		if not vcpkg["toolchain_present"]:
			details.append("toolchain missing")
		main_table.add_row(
			"vcpkg",
			"[bold yellow]WARN[/bold yellow]",
			", ".join(details) if details else "incomplete",
		)

	# --- Detected distro ---
	distro_id = state.get("distro_id")
	package_manager = state.get("package_manager")
	if distro_id:
		main_table.add_row(
			"Distro",
			"[bold green]OK[/bold green]",
			f"{distro_id} (pm: {package_manager or 'unknown'})",
		)
	else:
		main_table.add_row("Distro", "[bold yellow]WARN[/bold yellow]", "Not yet detected")

	return Group(Columns([main_table, deps_table], expand=True, equal=True))
