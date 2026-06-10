from pathlib import Path
import tomllib

STATE_DIR = Path.home() / ".config" / "BeamMP-Helper"
STATE_FILE = STATE_DIR / "state.toml"
APP_ROOT = Path.home() / ".local" / "share" / "BeamMP-Helper"
CACHE_ROOT = Path.home() / ".cache" / "BeamMP-Helper"
EXECUTABLE_PATH = Path.home() / ".local" / "bin" / "BeamMP-Helper"
DEFAULT_BEAMNG_ROOT = (
	Path.home() / ".local" / "share" / "BeamNG" / "BeamNG.drive" / "current"
)
DEFAULT_BEAMNG_MODS = DEFAULT_BEAMNG_ROOT / "mods"


def get_default_state() -> dict:
	return {
		"beamng_path": "",
		"beammp_binary_path": "",
		"steam_type": "none",
		"install_mode": "none",
		"last_check_timestamp": 0,
		"installed_version": "",
		"distro_id": "",
		"distro_family": "",
		"package_manager": "",
		"wrapper_installed": False,
		"language": "en",
	}


def load_state() -> dict:
	state = get_default_state()
	if not STATE_FILE.exists():
		return state
	try:
		with open(STATE_FILE, "rb") as file:
			loaded = tomllib.load(file)
			for key, val in loaded.items():
				if key in state:
					state[key] = val
	except (tomllib.TOMLDecodeError, OSError):
		pass
	return state


def save_state(state: dict) -> None:
	try:
		STATE_DIR.mkdir(parents=True, exist_ok=True)
		with open(STATE_FILE, "w", encoding="utf-8") as file:
			for key, val in state.items():
				if isinstance(val, bool):
					file.write(f"{key} = {str(val).lower()}\n")
				elif isinstance(val, (int, float)):
					file.write(f"{key} = {val}\n")
				elif isinstance(val, str):
					escaped = val.replace('"', '\\"')
					file.write(f'{key} = "{escaped}"\n')
	except OSError:
		pass
