from typer.testing import CliRunner

from converge.cli.main import app
from converge.exit_codes import ExitCode
from converge.version_info import package_version

runner = CliRunner()


def test_version_flag_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == ExitCode.SUCCESS
    assert package_version() in result.stdout
