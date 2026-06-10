from pathlib import Path
import tempfile
import tomllib
from beammp_helper.core.config import get_default_state, save_state
from beammp_helper.core.installer import _clean_vcpkg_openssl_buildtree


def test_default_state() -> None:
	state = get_default_state()
	assert "beamng_path" in state
	assert "beammp_binary_path" in state
	assert "steam_type" in state
	assert "install_mode" in state
	assert "last_check_timestamp" in state


def test_save_state_temp() -> None:
	state = get_default_state()
	state["beamng_path"] = "/mock/path"
	state["steam_type"] = "native"

	with tempfile.TemporaryDirectory() as temp_dir:
		temp_path = Path(temp_dir) / "state.toml"

		import beammp_helper.core.config

		old_file = beammp_helper.core.config.STATE_FILE
		old_dir = beammp_helper.core.config.STATE_DIR
		try:
			beammp_helper.core.config.STATE_FILE = temp_path
			beammp_helper.core.config.STATE_DIR = Path(temp_dir)

			save_state(state)

			assert temp_path.exists()
			with open(temp_path, "rb") as file:
				data = tomllib.load(file)
				assert data["beamng_path"] == "/mock/path"
				assert data["steam_type"] == "native"
		finally:
			beammp_helper.core.config.STATE_FILE = old_file
			beammp_helper.core.config.STATE_DIR = old_dir


def test_clean_vcpkg_openssl_buildtree() -> None:
	with tempfile.TemporaryDirectory() as temp_dir:
		vcpkg_dir = Path(temp_dir) / "vcpkg"
		openssl_buildtree = vcpkg_dir / "buildtrees" / "openssl"
		openssl_buildtree.mkdir(parents=True)
		marker = openssl_buildtree / "marker.txt"
		marker.write_text("stale build output", encoding="utf-8")

		assert _clean_vcpkg_openssl_buildtree(vcpkg_dir) is True
		assert not openssl_buildtree.exists()
		assert _clean_vcpkg_openssl_buildtree(vcpkg_dir) is False
