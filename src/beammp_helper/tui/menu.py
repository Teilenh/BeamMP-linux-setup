from pathlib import Path
import subprocess
import sys
import termios
import tty

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from beammp_helper.core.config import DEFAULT_BEAMNG_ROOT, load_state, save_state

from beammp_helper.core.detector import (
	check_build_dependencies,
	detect_beamng_game_path,
	detect_distro,
	get_build_dependency_cleanup_command,
	get_build_dependency_cleanup_packages,
	get_install_command,
	get_missing_dependencies,
	get_rpm_ostree_layered_packages,
	is_fedora_atomic,
	validate_beamng_game_path,
)
from beammp_helper.core.i18n import SUPPORTED_LANGUAGES, t
from beammp_helper.core.installer import install_beammp
from beammp_helper.core.launcher import get_launch_preflight_error, launch_beammp
from beammp_helper.core.integration import generate_desktop_entries, generate_wrapper
from beammp_helper.core.syscheck import build_system_check_table


def get_key() -> str:
	fd = sys.stdin.fileno()
	try:
		old_settings = termios.tcgetattr(fd)
	except termios.error:
		return sys.stdin.read(1)

	try:
		tty.setraw(fd)
		char = sys.stdin.read(1)
		if char == "\x1b":
			char += sys.stdin.read(2)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	return char


def show_system_check(console: Console) -> None:
	state = load_state()
	console.clear()

	console.print(build_system_check_table(state))

	console.print(f"\n{t('press_key_menu', state)}")
	get_key()


def run_installation_flow(console: Console) -> None:
	state = load_state()
	console.clear()
	console.print(f"[bold cyan]{t('install_title', state)}[/bold cyan]\n")

	deps = check_build_dependencies()
	missing = get_missing_dependencies(deps)

	if missing:
		console.print(f"[bold yellow]{t('missing_deps', state)}[/bold yellow]")
		for item in missing:
			console.print(f" - {item}")

		_, _, package_manager = detect_distro()
		if package_manager == "unknown":
			console.print(
				f"\n[bold red]{t('unknown_pm', state)}[/bold red]"
			)
			console.print(t("install_deps_manually", state))
			console.print(f"\n{t('press_key_menu', state)}")
			get_key()
			return

		cmd_steps = get_install_command(package_manager, missing)
		if cmd_steps:
			steps_display = " && ".join(" ".join(step) for step in cmd_steps)
			console.print(
				f"\n[bold green]{t('detected_pm', state)}[/bold green] {package_manager}"
			)
			if package_manager == "rpm-ostree":
				console.print(
					f"[bold yellow]{t('rpm_ostree_reboot_note', state)}[/bold yellow]"
				)
			console.print(
				f"{t('install_missing_prompt', state)}\n[bold]{steps_display}[/bold]\n(y/n): ",
				end="",
			)
			if input().strip().lower() == "y":
				console.clear()
				for step in cmd_steps:
					console.print(f"{t('running', state)} {' '.join(step)}\n")
					result = subprocess.run(step)
					if result.returncode != 0:
						console.print(
							f"\n[bold red]{t('command_failed', state)} (exit {result.returncode}): {' '.join(step)}[/bold red]"
						)
						console.print(t("press_key_menu", state))
						get_key()
						return
				if package_manager == "rpm-ostree":
					console.print(
						f"\n[bold yellow]{t('rpm_ostree_reboot_apply', state)}[/bold yellow]"
					)
					console.print(t("press_key_menu", state))
					get_key()
					return
				console.print(f"\n{t('continue_building', state)}")
				get_key()
			else:
				console.print(f"\n{t('abort_missing_deps', state)}")
				console.print(t("press_key_menu", state))
				get_key()
				return
		else:
			console.print(
				f"\n{t('no_install_command', state)}"
			)
			console.print(t("press_key_menu", state))
			get_key()
			return

	state = load_state()
	console.clear()
	console.print(f"[bold green]{t('starting_compile', state)}[/bold green]\n")

	def on_output(line: str) -> None:
		console.print(line, end="")

	success = install_beammp(state, on_output)

	if success:
		state = load_state()
		console.print(f"\n[bold green]{t('compiled_ok', state)}[/bold green]")
		# Desktop integration is opt-in.
		console.print(f"\n{t('desktop_entries_prompt', state)}", end="")
		if input().strip().lower() == "y":
			if generate_wrapper(state):
				state = load_state()
				if generate_desktop_entries(state):
					console.print(f"[bold green]{t('desktop_installed', state)}[/bold green]")
				else:
					console.print(f"[bold red]{t('desktop_write_failed', state)}[/bold red]")
			else:
				console.print(f"[bold red]{t('wrapper_failed', state)}[/bold red]")
	else:
		console.print(
			f"\n[bold red]{t('install_failed', state)}[/bold red]"
		)

	console.print(f"\n{t('press_key_menu', state)}")
	get_key()


def select_cleanup_packages(console: Console, packages: list[str]) -> list[str]:
	state = load_state()
	unselected_by_default = {"git", "tar", "unzip"}
	selected = [package not in unselected_by_default for package in packages]
	cursor = 0

	while True:
		console.clear()
		console.print(f"[bold cyan]{t('cleanup_title', state)}[/bold cyan]\n")
		console.print(f"[bold yellow]{t('zip_kept', state)}[/bold yellow]")
		console.print(f"{t('select_packages', state)}\n")

		for index, package in enumerate(packages):
			marker = "(X)" if selected[index] else "( )"
			line = f"{marker} {package}"
			if index == cursor:
				console.print(f"  [bold green]> {line}[/bold green]")
			else:
				console.print(f"    {line}")

		console.print(
			f"\n{t('checkbox_hint', state)}"
		)

		key = get_key()
		if key == "\x1b[A":
			cursor = (cursor - 1) % len(packages)
		elif key == "\x1b[B":
			cursor = (cursor + 1) % len(packages)
		elif key == " ":
			selected[cursor] = not selected[cursor]
		elif key.lower() == "a":
			selected = [True for _ in packages]
		elif key.lower() == "n":
			selected = [False for _ in packages]
		elif key.lower() == "q":
			return []
		elif key in ("\r", "\n"):
			return [
				package
				for package, is_selected in zip(packages, selected)
				if is_selected
			]


def run_build_dependency_cleanup(console: Console) -> None:
	state = load_state()
	console.clear()
	console.print(f"[bold cyan]{t('cleanup_title', state)}[/bold cyan]\n")
	console.print(t("cleanup_intro", state))
	console.print(f"[bold yellow]{t('zip_kept', state)}[/bold yellow]\n")

	_, _, package_manager = detect_distro()
	if package_manager == "unknown":
		console.print(f"[bold red]{t('unknown_pm', state)}[/bold red]")
		console.print(t("press_key_menu", state))
		get_key()
		return

	packages = get_build_dependency_cleanup_packages(package_manager)
	if not packages:
		if package_manager == "rpm-ostree":
			console.print(
				f"[bold green]{t('no_layers_to_remove', state)}[/bold green]"
			)
		else:
			console.print(
				f"[bold yellow]{t('no_cleanup_list', state)}[/bold yellow]"
			)
		console.print(f"\n{t('press_key_menu', state)}")
		get_key()
		return

	selected_packages = select_cleanup_packages(console, packages)
	if not selected_packages:
		console.clear()
		console.print(f"[bold yellow]{t('no_selected', state)}[/bold yellow]")
		console.print(f"\n{t('press_key_menu', state)}")
		get_key()
		return

	cmd_steps = get_build_dependency_cleanup_command(package_manager, selected_packages)
	if not cmd_steps:
		console.print(
			f"[bold red]{t('no_cleanup_command', state)}[/bold red]"
		)
		console.print(f"\n{t('press_key_menu', state)}")
		get_key()
		return

	console.print(f"[bold green]{t('detected_pm', state)}[/bold green] {package_manager}")
	console.print(f"\n{t('packages_removal', state)}")
	for package in selected_packages:
		console.print(f" - {package}")

	steps_display = " && ".join(" ".join(step) for step in cmd_steps)
	console.print(f"\n{t('command', state)}\n[bold]{steps_display}[/bold]")
	console.print(f"\n{t('cleanup_confirm', state)}", end="")
	if input().strip().lower() != "y":
		console.print(f"\n{t('cleanup_cancelled', state)}")
		console.print(t("press_key_menu", state))
		get_key()
		return

	console.clear()
	for step in cmd_steps:
		console.print(f"{t('running', state)} {' '.join(step)}\n")
		result = subprocess.run(step)
		if result.returncode != 0:
			console.print(
				f"\n[bold red]{t('command_failed', state)} (exit {result.returncode}): {' '.join(step)}[/bold red]"
			)
			console.print(t("press_key_menu", state))
			get_key()
			return

	if package_manager == "rpm-ostree":
		console.print(
			f"\n[bold yellow]{t('rpm_ostree_reboot_note', state)}[/bold yellow]"
		)
	console.print(f"\n[bold green]{t('cleanup_done', state)}[/bold green]")
	console.print(t("press_key_menu", state))
	get_key()


def run_rpm_ostree_cleanup(console: Console) -> None:
	state = load_state()
	console.clear()
	console.print(f"[bold cyan]{t('rpm_title', state)}[/bold cyan]\n")

	layered = get_rpm_ostree_layered_packages()

	if layered:
		console.print(f"[bold yellow]{t('layered_packages', state)}[/bold yellow]")
		for pkg in layered:
			console.print(f"  - {pkg}")
		console.print(
			f"\n{t('use_clean_deps', state)}"
		)
	else:
		console.print(f"[bold green]{t('no_layered', state)}[/bold green]")

	console.print(
		f"\n{t('rollback_prompt', state)}",
		end="",
	)
	ans = input().strip().lower()
	if ans == "y":
		console.clear()
		console.print(f"{t('running', state)} rpm-ostree rollback\n")
		subprocess.run(["rpm-ostree", "rollback"])
		console.print(
			f"\n[bold yellow]{t('reboot_required', state)}[/bold yellow]"
		)

	console.print(f"\n{t('press_key_menu', state)}")
	get_key()



def run_path_selection(console: Console) -> None:
	state = load_state()
	console.clear()
	console.print(f"[bold cyan]{t('path_title', state)}[/bold cyan]\n")

	console.print(f"1) {t('option_auto_path', state)}")
	console.print(f"2) {t('option_manual_path', state)}")
	console.print(f"3) {t('option_back', state)}")
	console.print("\n> ", end="")
	choice = input().strip()

	if choice == "1":
		auto_detect_beamng_path(console)
	elif choice == "2":
		set_beamng_path_manually(console)
	else:
		return

	console.print(f"\n{t('press_key_menu', state)}")
	get_key()


def auto_detect_beamng_path(console: Console) -> None:
	state = load_state()
	detected = detect_beamng_game_path()
	if detected:
		state["beamng_path"] = str(detected)
		save_state(state)
		console.print(f"\n[bold green]{t('auto_detect_ok', state)}[/bold green] {detected}")
	else:
		console.print(f"\n[bold red]{t('auto_detect_fail', state)}[/bold red]")


def set_beamng_path_manually(console: Console) -> None:
	state = load_state()
	console.print(f"\n{t('manual_path_prompt', state)}", end="")
	path_input = input().strip()
	path = Path(path_input).expanduser().resolve()
	if validate_beamng_game_path(path):
		state["beamng_path"] = str(path)
		save_state(state)
		console.print(f"\n[bold green]{t('path_valid', state)}[/bold green] {path}")
	else:
		console.print(f"\n[bold red]{t('path_invalid', state)}[/bold red]")


def create_desktop_integration(console: Console) -> None:
	state = load_state()
	if generate_wrapper(state):
		state = load_state()
		if generate_desktop_entries(state):
			console.print(f"\n[bold green]{t('desktop_entries_ok', state)}[/bold green]")
			return
	console.print(f"\n[bold red]{t('desktop_entries_fail', state)}[/bold red]")


def open_beamng_folder(console: Console) -> None:
	state = load_state()
	console.clear()
	userfolder = DEFAULT_BEAMNG_ROOT
	if not userfolder.exists():
		userfolder.mkdir(parents=True, exist_ok=True)
	console.print(f"{t('opening_folder', state)} {userfolder}\n")
	try:
		subprocess.Popen(["xdg-open", str(userfolder)])
		console.print(f"[bold green]{t('folder_opened', state)}[/bold green]")
	except OSError:
		console.print(f"[bold red]{t('folder_open_failed', state)}[/bold red]")

	console.print(f"\n{t('press_key_menu', state)}")
	get_key()


def run_language_menu(console: Console) -> None:
	state = load_state()
	language_items = list(SUPPORTED_LANGUAGES.items())
	selected_index = 0
	current_language = state.get("language", "en")
	for index, (code, _) in enumerate(language_items):
		if code == current_language:
			selected_index = index
			break

	while True:
		state = load_state()
		console.clear()
		console.print(f"[bold cyan]{t('language_title', state)}[/bold cyan]\n")
		console.print(f"{t('current_language', state)} {SUPPORTED_LANGUAGES.get(current_language, current_language)}\n")
		for index, (code, label) in enumerate(language_items):
			marker = "(X)" if code == current_language else "( )"
			line = f"{marker} {label}"
			if index == selected_index:
				console.print(f"  [bold green]> {line}[/bold green]")
			else:
				console.print(f"    {line}")
		console.print(f"\n{t('nav_hint', state)}")

		key = get_key()
		if key == "\x1b[A":
			selected_index = (selected_index - 1) % len(language_items)
		elif key == "\x1b[B":
			selected_index = (selected_index + 1) % len(language_items)
		elif key in ("\r", "\n"):
			current_language = language_items[selected_index][0]
			state["language"] = current_language
			save_state(state)
			console.print(f"\n[bold green]{t('language_saved', state)}[/bold green]")
			console.print(t("press_key_continue", state))
			get_key()
			return
		elif key.lower() == "q":
			return


def run_options_menu(console: Console) -> None:
	selected_index = 0

	while True:
		state = load_state()
		options = [
			("auto_path", t("option_auto_path", state)),
			("manual_path", t("option_manual_path", state)),
			("language", f"{t('option_language', state)}: {SUPPORTED_LANGUAGES.get(state.get('language', 'en'), 'English')}"),
			("desktop", t("option_desktop", state)),
			("open_folder", t("option_open_folder", state)),
			("back", t("option_back", state)),
		]
		console.clear()
		console.print(f"[bold cyan]{t('options_title', state)}[/bold cyan]\n")
		current_path = state.get("beamng_path") or "-"
		console.print(f"{t('path_title', state)}: {current_path}\n")

		for index, (_, label) in enumerate(options):
			if index == selected_index:
				console.print(f"  [bold green]> {label}[/bold green]")
			else:
				console.print(f"    {label}")

		console.print(f"\n{t('nav_hint', state)}")
		key = get_key()
		if key == "\x1b[A":
			selected_index = (selected_index - 1) % len(options)
		elif key == "\x1b[B":
			selected_index = (selected_index + 1) % len(options)
		elif key in ("\r", "\n"):
			action = options[selected_index][0]
			console.clear()
			if action == "auto_path":
				auto_detect_beamng_path(console)
				console.print(f"\n{t('press_key_menu', load_state())}")
				get_key()
			elif action == "manual_path":
				set_beamng_path_manually(console)
				console.print(f"\n{t('press_key_menu', load_state())}")
				get_key()
			elif action == "language":
				run_language_menu(console)
			elif action == "desktop":
				create_desktop_integration(console)
				console.print(f"\n{t('press_key_menu', load_state())}")
				get_key()
			elif action == "open_folder":
				open_beamng_folder(console)
			elif action == "back":
				return


def run_tui() -> None:
	console = Console()
	selected_index = 0

	while True:
		state = load_state()
		menu_items = [
			("launch", t("menu_launch", state)),
			("install", t("menu_install", state)),
			("check", t("menu_check", state)),
			("clean_deps", t("menu_clean_deps", state)),
			("options", t("menu_options", state)),
		]
		if is_fedora_atomic():
			menu_items.append(("rpm_ostree", t("menu_rpm_ostree", state)))
		menu_items.append(("exit", t("menu_exit", state)))
		if selected_index >= len(menu_items):
			selected_index = len(menu_items) - 1

		console.clear()
		console.print(
			Panel(
				Text(
					t("main_title", state),
					justify="center",
					style="bold cyan",
				),
				border_style="magenta",
			)
		)

		for index, (_, label) in enumerate(menu_items):
			if index == selected_index:
				console.print(f"  [bold green]> {label}[/bold green]")
			else:
				console.print(f"    {label}")

		console.print(f"\n{t('nav_hint', state)}")

		key = get_key()
		if key == "\x1b[A":
			selected_index = (selected_index - 1) % len(menu_items)
		elif key == "\x1b[B":
			selected_index = (selected_index + 1) % len(menu_items)
		elif key in ("\r", "\n"):
			choice = menu_items[selected_index][0]
			if choice == "launch":
				state = load_state()
				if not state.get("beamng_path") or not state.get("beammp_binary_path"):
					console.clear()
					console.print(
						f"[bold red]{t('launch_not_configured', state)}[/bold red]"
					)
					console.print(t("launch_config_hint", state))
					console.print(f"\n{t('press_key_menu', state)}")
					get_key()
				else:
					preflight_error = get_launch_preflight_error()
					if preflight_error:
						console.clear()
						console.print(
							f"[bold red]{t('launch_preflight_failed', state)}[/bold red] {preflight_error}"
						)
						console.print(f"\n{t('press_key_menu', state)}")
						get_key()
						continue

					success = launch_beammp()
					if not success:
						console.clear()
						console.print(
							f"[bold red]{t('launch_failed', state)}[/bold red]"
						)
						console.print(f"\n{t('press_key_menu', state)}")
						get_key()
					else:
						sys.exit(0)
			elif choice == "install":
				run_installation_flow(console)
			elif choice == "check":
				show_system_check(console)
			elif choice == "clean_deps":
				run_build_dependency_cleanup(console)
			elif choice == "options":
				run_options_menu(console)
			elif choice == "rpm_ostree":
				run_rpm_ostree_cleanup(console)
			elif choice == "exit":
				break
