import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.error



DEP_TO_PACKAGE = {
	"apt": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		"g++": ["build-essential"],
		"make": ["build-essential"],
		"pkg-config": ["pkg-config"],
		"perl": ["perl"],
		"perl-IPC-Cmd": [],
		"kernel-headers": ["linux-libc-dev"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
	"dnf": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		"g++": ["gcc", "gcc-c++"],
		"make": ["make"],
		"pkg-config": ["pkgconfig"],
		"perl": ["perl"],
		"perl-IPC-Cmd": [
			"perl-IPC-Cmd",
			"perl-FindBin",
			"perl-File-Compare",
			"perl-File-Copy",
		],
		"kernel-headers": ["kernel-headers", "kernel-devel"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
	"rpm-ostree": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		"g++": ["gcc", "gcc-c++"],
		"make": ["make"],
		"pkg-config": ["pkgconfig"],
		"perl": ["perl"],
		"perl-IPC-Cmd": [
			"perl-IPC-Cmd",
			"perl-FindBin",
			"perl-File-Compare",
			"perl-File-Copy",
		],
		"kernel-headers": ["kernel-headers", "kernel-devel"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
	"pacman": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		"g++": ["base-devel"],
		"make": ["base-devel"],
		"pkg-config": ["base-devel"],
		"perl": ["perl"],
		"perl-IPC-Cmd": [],
		"kernel-headers": ["linux-api-headers"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
	"zypper": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		# g++, make, pkg-config are covered by the 'devel_basis' pattern;
		# get_install_command() adds '-t pattern devel_basis' when these are missing.
		"g++": [],
		"make": [],
		"pkg-config": [],
		"perl": ["perl"],
		"perl-IPC-Cmd": [],
		"kernel-headers": ["kernel-devel"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
	"apk": {
		"git": ["git"],
		"cmake": ["cmake"],
		"curl": ["curl"],
		"g++": ["g++"],
		"make": ["make"],
		"pkg-config": ["pkgconfig"],
		"perl": ["perl"],
		"perl-IPC-Cmd": [],
		"kernel-headers": ["linux-headers"],
		"tar": ["tar"],
		"unzip": ["unzip"],
		"zip": ["zip"],
	},
}

BUILD_DEPENDENCIES = [
	"git",
	"cmake",
	"curl",
	"g++",
	"make",
	"pkg-config",
	"perl",
	"perl-IPC-Cmd",
	"kernel-headers",
	"tar",
	"unzip",
	"zip",
]

# zip is intentionally kept installed: it is small, broadly useful, and was
# explicitly requested as non-cleanup state.
BUILD_CLEANUP_DEPENDENCIES = [
	dep for dep in BUILD_DEPENDENCIES if dep != "zip"
]


def detect_steam_type() -> Tuple[str, Optional[Path]]:
	flatpak_steam = (
		Path.home()
		/ ".var"
		/ "app"
		/ "com.valvesoftware.Steam"
		/ ".local"
		/ "share"
		/ "Steam"
	)
	if flatpak_steam.exists():
		return "flatpak", flatpak_steam

	native_paths = [
		Path.home() / ".steam" / "steam",
		Path.home() / ".local" / "share" / "Steam",
		Path.home() / ".steam" / "root",
	]
	for path in native_paths:
		if path.exists():
			return "native", path

	return "none", None


def parse_library_folders(steam_path: Path) -> List[Path]:
	library_paths = [steam_path]
	vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
	if not vdf_path.exists():
		return library_paths

	try:
		with open(vdf_path, "r", encoding="utf-8") as file:
			content = file.read()
			matches = re.findall(r'"path"\s+"([^"]+)"', content)
			for match in matches:
				path = Path(match)
				if path.exists() and path not in library_paths:
					library_paths.append(path)
	except OSError:
		pass
	return library_paths


def detect_beamng_game_path() -> Optional[Path]:
	steam_type, steam_path = detect_steam_type()
	if not steam_path:
		return None

	library_paths = parse_library_folders(steam_path)
	for lib in library_paths:
		candidate = lib / "steamapps" / "common" / "BeamNG.drive"
		if candidate.exists() and validate_beamng_game_path(candidate):
			return candidate
	return None


def validate_beamng_game_path(path: Path) -> bool:
	if not path.exists() or not path.is_dir():
		return False
	linux_exe = path / "BinLinux" / "BeamNG.drive.x86_64"
	win_exe = path / "Bin64" / "BeamNG.drive.exe"
	return linux_exe.exists() or win_exe.exists() or (path / "BinLinux").is_dir()


def validate_beamng_userfolder(path: Path) -> bool:
	try:
		if not path.exists():
			path.mkdir(parents=True, exist_ok=True)
		mods_dir = path / "mods"
		if not mods_dir.exists():
			mods_dir.mkdir(parents=True, exist_ok=True)
		return os.access(path, os.W_OK) and os.access(mods_dir, os.W_OK)
	except OSError:
		return False


# Maps /etc/os-release ID values to (family, package_manager).
# Fedora Atomic variants are handled before this table via is_fedora_atomic().
DISTRO_FAMILY_MAP: Dict[str, Tuple[str, str]] = {
	"debian":               ("debian",    "apt"),
	"ubuntu":               ("debian",    "apt"),
	"linuxmint":            ("debian",    "apt"),
	"pop":                  ("debian",    "apt"),
	"pikaos":               ("debian",    "apt"),
	"fedora":               ("fedora",    "dnf"),
	"arch":                 ("arch",      "pacman"),
	"endeavouros":          ("arch",      "pacman"),
	"cachyos":              ("arch",      "pacman"),
	"opensuse-leap":        ("opensuse",  "zypper"),
	"opensuse-tumbleweed":  ("opensuse",  "zypper"),
	"opensuse-slowroll":    ("opensuse",  "zypper"),
	"alpine":               ("alpine",    "apk"),
	"steamos":              ("steamos",   "pacman"),
}


def detect_distro() -> Tuple[str, str, str]:
	"""
	Return (distro_id, family, package_manager) by reading /etc/os-release.

	Priority order:
	  1. Fedora Atomic override (Silverblue, Kinoite, Bazzite …) → rpm-ostree
	  2. Exact ID match in DISTRO_FAMILY_MAP
	  3. ID_LIKE fallback for derivatives (e.g. Kali → debian)
	  4. Unknown — caller must handle gracefully
	"""
	fields = _read_os_release()
	distro_id = fields.get("ID", "").lower()
	id_like = fields.get("ID_LIKE", "").lower().split()

	# Must be checked before the generic 'fedora' entry, because Bazzite/Silverblue
	# also have dnf on PATH and would otherwise be misdetected.
	if is_fedora_atomic():
		return distro_id, "fedora_atomic", "rpm-ostree"

	if distro_id in DISTRO_FAMILY_MAP:
		family, pm = DISTRO_FAMILY_MAP[distro_id]
		return distro_id, family, pm

	for like in id_like:
		if like in DISTRO_FAMILY_MAP:
			family, pm = DISTRO_FAMILY_MAP[like]
			return distro_id, family, pm

	return distro_id, "unknown", "unknown"


def _perl_ipc_cmd_available() -> bool:
	perl = shutil.which("perl")
	if perl is None:
		return False
	try:
		result = subprocess.run(
			[perl, "-MIPC::Cmd", "-e", "1"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)
		return result.returncode == 0
	except OSError:
		return False


def check_build_dependencies() -> Dict[str, bool]:
	gxx_ok = shutil.which("g++") is not None or shutil.which("clang++") is not None
	make_ok = shutil.which("make") is not None or shutil.which("ninja") is not None
	kernel_headers_ok = Path("/usr/include/linux/version.h").exists()
	return {
		"git": shutil.which("git") is not None,
		"cmake": shutil.which("cmake") is not None,
		"curl": shutil.which("curl") is not None,
		"g++": gxx_ok,
		"make": make_ok,
		"pkg-config": shutil.which("pkg-config") is not None,
		"perl": shutil.which("perl") is not None,
		"perl-IPC-Cmd": _perl_ipc_cmd_available(),
		"kernel-headers": kernel_headers_ok,
		"tar": shutil.which("tar") is not None,
		"unzip": shutil.which("unzip") is not None,
		"zip": shutil.which("zip") is not None,
	}


def check_hostname_resolution(hostname: str = "backend.beammp.com") -> Tuple[bool, str]:
	try:
		addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
	except socket.gaierror as err:
		return False, f"DNS resolution failed for {hostname}: {err}"
	except OSError as err:
		return False, f"Network check failed for {hostname}: {err}"

	if not addresses:
		return False, f"DNS resolution returned no address for {hostname}"

	ip = addresses[0][4][0]
	return True, f"{hostname} resolves to {ip}"


def get_missing_dependencies(deps: Dict[str, bool]) -> List[str]:
	missing = []
	for dep, installed in deps.items():
		if not installed:
			missing.append(dep)
	return missing


def _read_os_release() -> Dict[str, str]:
	fields: Dict[str, str] = {}
	try:
		with open("/etc/os-release", "r", encoding="utf-8") as file:
			for raw_line in file:
				line = raw_line.strip()
				if "=" not in line or line.startswith("#"):
					continue
				key, _, value = line.partition("=")
				fields[key] = value.strip('"')
	except OSError:
		pass
	return fields


ATOMIC_VARIANT_IDS = {
	"silverblue",
	"kinoite",
	"sericea",
	"onyx",
	"iot",
	"coreos",
}


def is_fedora_atomic() -> bool:
	fields = _read_os_release()
	variant_id = fields.get("VARIANT_ID", "").lower()
	if variant_id in ATOMIC_VARIANT_IDS:
		return True
	if fields.get("ID", "").lower() == "fedora" and shutil.which("rpm-ostree") is not None:
		return True
	return False


def is_steamos() -> bool:
	fields = _read_os_release()
	return fields.get("ID", "").lower() == "steamos" or "steamos" in fields.get("NAME", "").lower()


def get_rpm_ostree_layered_packages() -> List[str]:
	rpm_ostree = shutil.which("rpm-ostree")
	if rpm_ostree is None:
		return []
	try:
		result = subprocess.run(
			[rpm_ostree, "status", "--json"],
			stdout=subprocess.PIPE,
			stderr=subprocess.DEVNULL,
			text=True,
		)
		if result.returncode != 0:
			return []
		data = json.loads(result.stdout)
	except (OSError, json.JSONDecodeError):
		return []

	packages: List[str] = []
	for deployment in data.get("deployments", []):
		if not deployment.get("booted", False):
			continue
		for pkg in deployment.get("requested-local-packages", []):
			if pkg not in packages:
				packages.append(pkg)
		for pkg in deployment.get("requested-packages", []):
			if pkg not in packages:
				packages.append(pkg)
		break
	return packages


def get_install_command(manager: str, missing_deps: List[str]) -> Optional[List[List[str]]]:
	"""
	Return a list of command steps needed to install missing_deps, or None.

	Each step is a List[str] safe to pass to subprocess.run() with shell=False.
	Multiple steps must be run sequentially; all must succeed.
	"""
	# SteamOS requires temporarily disabling the read-only filesystem.
	if manager == "pacman" and is_steamos():
		return [
			["sudo", "steamos-readonly", "disable"],
			["sudo", "pacman", "-S", "--needed", "--noconfirm",
			 "git", "cmake", "base-devel", "linux-api-headers", "glibc", "libconfig",
			 "curl", "zip", "unzip", "tar"],
			["sudo", "steamos-readonly", "enable"],
		]

	# openSUSE: g++/make/pkg-config come from the 'devel_basis' pattern group.
	if manager == "zypper":
		has_pattern = any(d in missing_deps for d in ["g++", "make", "pkg-config"])
		cmd = ["sudo", "zypper", "install", "-y"]
		if has_pattern:
			cmd += ["-t", "pattern", "devel_basis"]
		pkgs = [
			pkg
			for dep in missing_deps
			for pkg in DEP_TO_PACKAGE["zypper"].get(dep, [])
		]
		pkgs = list(dict.fromkeys(pkgs))
		if not pkgs and not has_pattern:
			return None
		return [cmd + pkgs]

	manager_map = DEP_TO_PACKAGE.get(manager)
	if not manager_map:
		return None

	packages: List[str] = []
	for dep in missing_deps:
		for pkg in manager_map.get(dep, []):
			if pkg not in packages:
				packages.append(pkg)

	if not packages:
		return None

	if manager == "apt":
		# apt needs an index refresh before install.
		return [
			["sudo", "apt", "update"],
			["sudo", "apt", "install", "-y"] + packages,
		]
	elif manager == "dnf":
		return [["sudo", "dnf", "install", "-y"] + packages]
	elif manager == "rpm-ostree":
		return [["rpm-ostree", "install"] + packages]
	elif manager == "pacman":
		return [["sudo", "pacman", "-S", "--needed", "--noconfirm"] + packages]
	elif manager == "apk":
		return [["sudo", "apk", "add"] + packages]
	return None


def _packages_for_dependencies(manager: str, deps: List[str]) -> List[str]:
	manager_map = DEP_TO_PACKAGE.get(manager)
	if not manager_map:
		return []

	packages: List[str] = []
	for dep in deps:
		for pkg in manager_map.get(dep, []):
			if pkg not in packages:
				packages.append(pkg)
	return packages


def get_build_dependency_cleanup_packages(manager: str) -> List[str]:
	packages = _packages_for_dependencies(manager, BUILD_CLEANUP_DEPENDENCIES)

	if manager == "rpm-ostree":
		layered = set(get_rpm_ostree_layered_packages())
		packages = [pkg for pkg in packages if pkg in layered]

	if manager == "pacman":
		# base-devel is a group on Arch-like systems, not a precise cleanup target.
		packages = [pkg for pkg in packages if pkg != "base-devel"]

	return packages


def get_build_dependency_cleanup_command(
	manager: str, packages: Optional[List[str]] = None
) -> Optional[List[List[str]]]:
	if packages is None:
		packages = get_build_dependency_cleanup_packages(manager)
	if not packages:
		return None

	if manager == "apt":
		return [["sudo", "apt", "remove", "-y"] + packages]
	if manager == "dnf":
		return [["sudo", "dnf", "remove", "-y"] + packages]
	if manager == "rpm-ostree":
		return [["rpm-ostree", "uninstall"] + packages]
	if manager == "pacman":
		return [["sudo", "pacman", "-Rns", "--noconfirm"] + packages]
	if manager == "zypper":
		return [["sudo", "zypper", "remove", "-y"] + packages]
	if manager == "apk":
		return [["sudo", "apk", "del"] + packages]
	return None


def check_vcpkg_state(vcpkg_dir: Path) -> Dict[str, bool]:
	vcpkg_exe = vcpkg_dir / "vcpkg"
	bootstrap_script = vcpkg_dir / "bootstrap-vcpkg.sh"
	toolchain = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
	return {
		"cloned": vcpkg_dir.is_dir() and bootstrap_script.exists(),
		"bootstrapped": vcpkg_exe.is_file(),
		"toolchain_present": toolchain.is_file(),
	}


def get_installed_beammp_version(binary_path: Path) -> Optional[str]:
	if not binary_path.is_file():
		return None
	try:
		result = subprocess.run(
			[str(binary_path), "--version"],
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			timeout=5,
		)
		for line in result.stdout.splitlines():
			match = re.search(r"(\d+\.\d+\.\d+)", line)
			if match:
				return match.group(1)
	except (OSError, subprocess.TimeoutExpired):
		pass
	return None


def check_beammp_update_available(
	installed_version: Optional[str],
) -> Tuple[bool, Optional[str]]:
	try:
		request = urllib.request.Request(
			"https://api.github.com/repos/BeamMP/BeamMP-Launcher/releases/latest",
			headers={"Accept": "application/vnd.github+json", "User-Agent": "BeamMP-Helper"},
		)
		with urllib.request.urlopen(request, timeout=8) as response:
			data = json.loads(response.read().decode())
		latest_tag: str = data.get("tag_name", "").lstrip("v")
	except (urllib.error.URLError, json.JSONDecodeError, OSError):
		return False, None

	if not latest_tag:
		return False, None

	if installed_version is None:
		return True, latest_tag

	def version_tuple(version_string: str) -> tuple:
		try:
			return tuple(int(part) for part in version_string.split("."))
		except ValueError:
			return (0,)

	update_available = version_tuple(latest_tag) > version_tuple(installed_version)
	return update_available, latest_tag
