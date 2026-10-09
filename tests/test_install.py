"""The data API works without the "render" extra (Playwright) installed."""

import subprocess
import sys
import textwrap

# With None in sys.modules, `import playwright` fails just as if it were not installed.
BLOCK_PLAYWRIGHT = "import sys; sys.modules['playwright'] = None\n"


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", BLOCK_PLAYWRIGHT + textwrap.dedent(code)], capture_output=True, text=True
    )


def test_data_api_imports_without_playwright():
    result = run(
        """
        import geoguessr_avatar as ga
        from geoguessr_avatar import BrowserNotInstalled, GeoGuessrClient, Slot, animations, parse_user_id

        assert "geoguessr_avatar.renderer" not in sys.modules
        try:
            ga.AvatarRenderer
        except ImportError as exc:
            assert "geoguessr-avatar[render]" in str(exc), exc
        else:
            raise SystemExit("expected an ImportError naming the render extra")
        """
    )
    assert result.returncode == 0, result.stderr


def test_cli_lists_animations_without_playwright():
    result = run("from geoguessr_avatar.__main__ import main\nraise SystemExit(main(['animations']))")
    assert result.returncode == 0, result.stderr
    assert "IDLE" in result.stdout
