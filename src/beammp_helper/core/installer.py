import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, List, Optional
import urllib.error
import urllib.request

from beammp_helper.core.config import APP_ROOT, CACHE_ROOT, save_state
from beammp_helper.core.detector import check_build_dependencies


def run_build_command(
	args: List[str],
	cwd: Path,
	on_output: Optional[Callable[[str], None]] = None,
	env: Optional[dict] = None,
) -> int:
	try:
		process = subprocess.Popen(
			args,
			cwd=str(cwd),
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			bufsize=1,
			env=env,
		)
		if process.stdout:
			for line in process.stdout:
				if on_output:
					on_output(line)
		return process.wait()
	except OSError:
		return -1


def _fetch_latest_launcher_tag() -> Optional[str]:
	try:
		request = urllib.request.Request(
			"https://api.github.com/repos/BeamMP/BeamMP-Launcher/releases/latest",
			headers={"Accept": "application/vnd.github+json", "User-Agent": "BeamMP-Helper"},
		)
		with urllib.request.urlopen(request, timeout=10) as response:
			data = json.loads(response.read().decode())
		tag: str = data.get("tag_name", "")
		return tag if tag else None
	except (urllib.error.URLError, json.JSONDecodeError, OSError):
		return None


def _build_subprocess_env(vcpkg_dir: Path) -> dict:
	env = os.environ.copy()
	env["VCPKG_ROOT"] = str(vcpkg_dir)
	env["PATH"] = str(vcpkg_dir) + os.pathsep + env.get("PATH", "")
	return env


def _clean_vcpkg_openssl_buildtree(vcpkg_dir: Path) -> bool:
	openssl_buildtree = vcpkg_dir / "buildtrees" / "openssl"
	if not openssl_buildtree.exists():
		return False
	try:
		shutil.rmtree(openssl_buildtree)
		return True
	except OSError:
		return False


def install_beammp(
	state: dict, on_output: Optional[Callable[[str], None]] = None
) -> bool:
	deps = check_build_dependencies()
	for dep, installed in deps.items():
		if not installed:
			if on_output:
				on_output(f"Error: Missing build dependency: {dep}\n")
			return False

	CACHE_ROOT.mkdir(parents=True, exist_ok=True)
	APP_ROOT.mkdir(parents=True, exist_ok=True)

	vcpkg_dir = CACHE_ROOT / "vcpkg"
	if not vcpkg_dir.exists():
		if on_output:
			on_output("Cloning vcpkg...\n")
		ret = run_build_command(
			["git", "clone", "--depth=1", "https://github.com/microsoft/vcpkg.git", str(vcpkg_dir)],
			CACHE_ROOT,
			on_output,
		)
		if ret != 0:
			if on_output:
				on_output("Failed to clone vcpkg\n")
			return False

	vcpkg_exe = vcpkg_dir / "vcpkg"
	if not vcpkg_exe.exists():
		if on_output:
			on_output("Bootstrapping vcpkg...\n")
		ret = run_build_command(
			["./bootstrap-vcpkg.sh", "-disableMetrics"],
			vcpkg_dir,
			on_output,
		)
		if ret != 0:
			if on_output:
				on_output("Failed to bootstrap vcpkg\n")
			return False

	build_env = _build_subprocess_env(vcpkg_dir)

	if on_output:
		on_output("Fetching latest BeamMP-Launcher release tag...\n")
	latest_tag = _fetch_latest_launcher_tag()
	if latest_tag:
		if on_output:
			on_output(f"Latest release: {latest_tag}\n")
	else:
		if on_output:
			on_output("Could not fetch latest tag, will build HEAD\n")

	launcher_dir = CACHE_ROOT / "BeamMP-Launcher"
	if launcher_dir.exists():
		try:
			shutil.rmtree(launcher_dir)
		except OSError:
			pass

	if on_output:
		on_output("Cloning BeamMP-Launcher...\n")
	ret = run_build_command(
		["git", "clone", "https://github.com/BeamMP/BeamMP-Launcher.git", str(launcher_dir)],
		CACHE_ROOT,
		on_output,
	)
	if ret != 0:
		if on_output:
			on_output("Failed to clone BeamMP-Launcher\n")
		return False

	if latest_tag:
		if on_output:
			on_output(f"Checking out {latest_tag}...\n")
		ret = run_build_command(
			["git", "checkout", latest_tag],
			launcher_dir,
			on_output,
		)
		if ret != 0:
			if on_output:
				on_output(f"Failed to checkout tag {latest_tag}, continuing on HEAD\n")

	toolchain = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
	if on_output:
		on_output("Configuring CMake...\n")

	make_program = shutil.which("ninja") or shutil.which("make")
	c_compiler = shutil.which("gcc") or shutil.which("clang")
	cxx_compiler = shutil.which("g++") or shutil.which("clang++")
	cmake_generator = "Ninja" if shutil.which("ninja") else "Unix Makefiles"

	cmake_args = [
		"cmake",
		".",
		"-B",
		"bin",
		f"-G{cmake_generator}",
		f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
		"-DVCPKG_TARGET_TRIPLET=x64-linux",
	]
	if make_program:
		cmake_args.append(f"-DCMAKE_MAKE_PROGRAM={make_program}")
	if c_compiler:
		cmake_args.append(f"-DCMAKE_C_COMPILER={c_compiler}")
	if cxx_compiler:
		cmake_args.append(f"-DCMAKE_CXX_COMPILER={cxx_compiler}")

	ret = run_build_command(cmake_args, launcher_dir, on_output, env=build_env)
	if ret != 0:
		if on_output:
			on_output(
				"CMake configuration failed. Cleaning vcpkg OpenSSL build cache and retrying once...\n"
			)
		cleaned = _clean_vcpkg_openssl_buildtree(vcpkg_dir)
		if on_output and not cleaned:
			on_output("No vcpkg OpenSSL build cache was found to clean.\n")
		ret = run_build_command(cmake_args, launcher_dir, on_output, env=build_env)
	if ret != 0:
		if on_output:
			on_output("Failed to configure CMake\n")
		return False

	if on_output:
		on_output("Building BeamMP-Launcher...\n")
	ret = run_build_command(
		["cmake", "--build", "bin", "--parallel"],
		launcher_dir,
		on_output,
		env=build_env,
	)
	if ret != 0:
		if on_output:
			on_output("Failed to build BeamMP-Launcher\n")
		return False

	built_bin = launcher_dir / "bin" / "BeamMP-Launcher"
	if not built_bin.exists():
		if on_output:
			on_output("Built binary not found at standard path\n")
		return False

	dest_bin = APP_ROOT / "BeamMP-Launcher"
	try:
		if dest_bin.exists():
			dest_bin.unlink()
		shutil.copy2(built_bin, dest_bin)
		os.chmod(dest_bin, 0o755)
	except OSError as err:
		if on_output:
			on_output(f"Failed to copy binary to destination: {err}\n")
		return False

	state["beammp_binary_path"] = str(dest_bin)
	state["install_mode"] = "source"
	if latest_tag:
		state["installed_version"] = latest_tag.lstrip("v")
	save_state(state)

	if on_output:
		on_output(f"Successfully installed BeamMP to {dest_bin}\n")
	return True
