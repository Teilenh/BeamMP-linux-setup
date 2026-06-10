import os
from pathlib import Path
from beammp_helper.core.config import DEFAULT_BEAMNG_ROOT, load_state
from beammp_helper.core.detector import (
	validate_beamng_game_path,
	validate_beamng_userfolder,
)


def get_launch_preflight_errors() -> list[str]:
	errors: list[str] = []
	state = load_state()
	beamng_path_str = state.get("beamng_path")
	beammp_binary_str = state.get("beammp_binary_path")

	if not beamng_path_str or not beammp_binary_str:
		errors.append("BeamNG.drive path or BeamMP binary path is not configured.")
		return errors

	beamng_path = Path(beamng_path_str)
	beammp_binary = Path(beammp_binary_str)

	if not validate_beamng_game_path(beamng_path):
		errors.append(f"BeamNG.drive path is invalid: {beamng_path}")

	if not beammp_binary.exists():
		errors.append(f"BeamMP launcher binary is missing: {beammp_binary}")

	userfolder = DEFAULT_BEAMNG_ROOT
	if not validate_beamng_userfolder(userfolder):
		errors.append(f"BeamNG userfolder cannot be accessed or created: {userfolder}")

	return errors


def get_launch_preflight_error() -> str:
	return "\n".join(get_launch_preflight_errors())


def launch_beammp() -> bool:
	state = load_state()
	beamng_path_str = state.get("beamng_path")
	beammp_binary_str = state.get("beammp_binary_path")

	if get_launch_preflight_error():
		return False

	beamng_path = Path(beamng_path_str)
	beammp_binary = Path(beammp_binary_str)
	userfolder = DEFAULT_BEAMNG_ROOT

	env = dict(os.environ)
	env["BEAMNG_PATH"] = str(beamng_path)
	env["BEAMNG_USERFOLDER"] = str(userfolder)

	try:
		os.execve(str(beammp_binary), [str(beammp_binary)], env)
	except OSError:
		return False
