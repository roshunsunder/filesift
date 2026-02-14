import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import click
from pathlib import Path
from typing import Optional


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """FileSift - Intelligent file indexing and search system"""
    pass


@cli.command()
@click.argument("query", required=True)
@click.option("--path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
              help="Directory to search in (defaults to current directory)")
def find(query: str, path: Optional[Path]):
    """Search for files using a query string"""
    search_dir = Path(path) if path else Path.cwd()
    index_dir = search_dir / ".filesift"

    if not index_dir.exists():
        click.echo(f"Error: No index found in {search_dir}", err=True)
        click.echo(f"\nTo create an index, run:", err=True)
        click.echo(f"  filesift index {search_dir}", err=True)
        raise click.Abort()

    from filesift.cli.daemon_utils import is_daemon_running, get_daemon_url, ensure_daemon_running
    import requests
    from filesift._core.query import SearchResult

    ensure_daemon_running()

    if is_daemon_running():
        try:
            url = get_daemon_url()
            response = requests.post(
                f"{url}/search",
                json={
                    "index_path": str(index_dir),
                    "query": query,
                    "filters": {}
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            results = [
                SearchResult(path=r["path"], score=r["score"], metadata=r["metadata"])
                for r in data["results"]
            ]

            _print_results(results)
            return
        except Exception as e:
            click.echo(f"Daemon error: {e}", err=True)
            click.echo("Falling back to local search...", err=True)

    try:
        from filesift._core.query import QueryDriver
    except ImportError:
        click.echo("Error: Couldn't load QueryDriver.", err=True)
        raise click.Abort()

    try:
        print("Loading index...")
        query_driver = QueryDriver()
        query_driver.load_from_disk(str(index_dir))

        click.echo(f"Searching for: {query}")
        results = query_driver.search(query)
        _print_results(results)

    except Exception as e:
        click.echo(f"Error during search: {e}", err=True)
        raise click.Abort()


def _print_results(results) -> None:
    """Format and print search results."""
    if not results:
        click.echo("No results found.")
        return

    click.echo(f"\nFound {len(results)} result(s):\n")
    for i, result in enumerate(results, 1):
        click.echo(f"{i}. {result.path}")
        parts = []
        if result.metadata.get("language"):
            parts.append(f"Language: {result.metadata['language']}")
        if result.metadata.get("line_count"):
            parts.append(f"Lines: {result.metadata['line_count']}")
        if result.score:
            parts.append(f"Score: {result.score:.4f}")
        if parts:
            click.echo(f"   {' | '.join(parts)}")
        click.echo()


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--reindex", is_flag=True, help="Force a complete reindex, overwriting any existing index")
def index(path: Path, reindex: bool):
    """Index a directory for search"""
    try:
        from filesift._core.indexer import Indexer
    except ImportError:
        click.echo("Couldn't load indexer.", err=True)
        raise click.Abort()

    try:
        indexer = Indexer(root=path)
        indexer.index(reindex=reindex)
        click.echo("Indexing complete.")

        from filesift.cli.daemon_utils import ensure_daemon_running, get_daemon_url
        import requests

        index_dir = path / ".filesift"
        if ensure_daemon_running():
            try:
                url = get_daemon_url()
                click.echo("Notifying daemon to reload index...")
                response = requests.post(
                    f"{url}/reload",
                    json={"index_path": str(index_dir)},
                    timeout=10
                )
                if response.status_code == 202:
                    click.echo("Daemon is reloading the index in the background.")
                    click.echo("Run 'filesift daemon status' to check progress.")
                else:
                    response.raise_for_status()
            except Exception as e:
                click.echo(f"Warning: Could not reload index in daemon: {e}", err=True)

    except Exception as e:
        click.echo(f"Error during indexing: {e}", err=True)
        raise click.Abort()


@cli.group()
def config():
    """Manage configuration settings"""
    pass


@config.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
def set(key: str, value: str):
    """Set a configuration value

    KEY format: section.KEY (e.g., search.MAX_RESULTS, daemon.PORT)
    """
    from filesift._config.config import load_config, save_config, get_default_config

    if "." not in key:
        click.echo(f"Error: Key must be in format 'section.KEY' (e.g., 'search.MAX_RESULTS')", err=True)
        raise click.Abort()

    section_name, config_key = key.split(".", 1)

    default_config = get_default_config()

    if section_name not in default_config:
        click.echo(f"Error: Section '{section_name}' not found in configuration", err=True)
        click.echo(f"Available sections: {', '.join(default_config.keys())}", err=True)
        raise click.Abort()

    if config_key not in default_config[section_name]:
        click.echo(f"Error: Key '{config_key}' not found in section '{section_name}'", err=True)
        click.echo(f"Available keys in '{section_name}': {', '.join(default_config[section_name].keys())}", err=True)
        raise click.Abort()

    expected_value = default_config[section_name][config_key]
    expected_type = type(expected_value)

    try:
        if expected_type == bool:
            if value.lower() in ("true", "1", "yes", "on"):
                parsed_value = True
            elif value.lower() in ("false", "0", "no", "off"):
                parsed_value = False
            else:
                click.echo(f"Error: Invalid boolean value '{value}'. Use 'true' or 'false'", err=True)
                raise click.Abort()
        elif expected_type == int:
            parsed_value = int(value)
        elif expected_type == float:
            parsed_value = float(value)
        elif expected_type == list:
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = value[1:-1].strip()
            if not value:
                parsed_value = []
            elif "," in value:
                parsed_value = [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]
            else:
                parsed_value = [item.strip().strip('"').strip("'") for item in value.split() if item.strip()]
        else:
            parsed_value = value
    except ValueError as e:
        click.echo(f"Error: Could not parse value '{value}' as {expected_type.__name__}: {e}", err=True)
        raise click.Abort()

    current_config = load_config()

    if section_name not in current_config:
        current_config[section_name] = {}

    old_value = current_config[section_name].get(config_key, "not set")
    current_config[section_name][config_key] = parsed_value

    try:
        save_config(current_config)
        click.echo(f"Set {key} = {parsed_value} (was: {old_value})")

        import filesift._config.config as config_module
        config_module.config_dict = load_config()
        click.echo("Configuration updated. Changes will take effect in new processes.")
    except Exception as e:
        click.echo(f"Error saving configuration: {e}", err=True)
        raise click.Abort()


@config.command("list")
@click.argument("section", required=False)
@click.option("--all", "show_all", is_flag=True, help="Show all sections with their keys and values")
def list_config(section: Optional[str], show_all: bool):
    """List configuration sections and their keys/values

    Without arguments, lists all available sections.
    With a section name, shows keys and values for that section.
    Use --all to show all sections with their keys and values.
    """
    from filesift._config.config import load_config, get_default_config

    current_config = load_config()
    default_config = get_default_config()

    def format_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, list):
            if not value:
                return "[]"
            items = [str(item) for item in value[:3]]
            if len(value) > 3:
                items.append(f"... ({len(value)} total)")
            return "[" + ", ".join(items) + "]"
        elif isinstance(value, str) and len(value) > 50:
            return value[:47] + "..."
        else:
            return str(value)

    if show_all:
        for section_name in sorted(default_config.keys()):
            click.echo(f"\n[{section_name}]")
            section_config = current_config.get(section_name, default_config[section_name])

            for key in sorted(default_config[section_name].keys()):
                if key in section_config:
                    value = section_config[key]
                    default_value = default_config[section_name][key]
                    if value != default_value:
                        click.echo(f"  {key} = {format_value(value)} (default: {format_value(default_value)})")
                    else:
                        click.echo(f"  {key} = {format_value(value)}")
                else:
                    default_value = default_config[section_name][key]
                    click.echo(f"  {key} = {format_value(default_value)} (default)")
        click.echo()
    elif section:
        if section not in default_config:
            click.echo(f"Error: Section '{section}' not found in configuration", err=True)
            click.echo(f"Available sections: {', '.join(sorted(default_config.keys()))}", err=True)
            raise click.Abort()

        click.echo(f"[{section}]")
        section_config = current_config.get(section, default_config[section])

        for key in sorted(default_config[section].keys()):
            if key in section_config:
                value = section_config[key]
                default_value = default_config[section][key]
                if value != default_value:
                    click.echo(f"  {key} = {format_value(value)} (default: {format_value(default_value)})")
                else:
                    click.echo(f"  {key} = {format_value(value)}")
            else:
                default_value = default_config[section][key]
                click.echo(f"  {key} = {format_value(default_value)} (default)")
    else:
        click.echo("Available configuration sections:")
        for section_name in sorted(default_config.keys()):
            key_count = len(default_config[section_name])
            click.echo(f"  {section_name} ({key_count} key{'s' if key_count != 1 else ''})")
        click.echo("\nUse 'filesift config list <section>' to see keys and values for a section.")
        click.echo("Use 'filesift config list --all' to see all sections with their keys and values.")


@config.command("add-ignore")
@click.option("-f", "--file", "file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Add ignore patterns from a file (similar to .gitignore)")
@click.argument("patterns", nargs=-1, required=False)
def add_ignore(file_path: Optional[Path], patterns: tuple):
    """Add ignore patterns"""
    from filesift._config.config import load_config, save_config

    if not file_path and not patterns:
        click.echo("Error: Must provide either --file or patterns", err=True)
        return

    new_patterns = []
    if file_path:
        try:
            file_patterns = [line.strip() for line in file_path.read_text().splitlines()]
            file_patterns = [p for p in file_patterns if p and not p.startswith("#")]
            new_patterns.extend(file_patterns)
        except Exception as e:
            click.echo(f"Error reading patterns from file: {e}", err=True)
            return

    if patterns:
        new_patterns.extend([p.strip() for p in patterns if p.strip()])

    if not new_patterns:
        click.echo("No valid patterns provided.", err=True)
        return

    current_config = load_config()
    excluded_dirs = current_config.get("indexing", {}).get("EXCLUDED_DIRS", [])

    added = []
    for pattern in new_patterns:
        if pattern not in excluded_dirs:
            excluded_dirs.append(pattern)
            added.append(pattern)

    if not added:
        click.echo("No new patterns were added (all already present).")
        return

    current_config.setdefault("indexing", {})["EXCLUDED_DIRS"] = excluded_dirs
    save_config(current_config)
    import filesift._config.config as config_module
    config_module.config_dict = load_config()

    click.echo("Added ignore patterns:")
    for pattern in added:
        click.echo(f"  {pattern}")


@config.command("remove-ignore")
@click.argument("pattern", required=True)
def remove_ignore(pattern: str):
    """Remove an ignore pattern"""
    from filesift._config.config import load_config, save_config

    current_config = load_config()
    excluded_dirs = current_config.get("indexing", {}).get("EXCLUDED_DIRS", [])

    if pattern not in excluded_dirs:
        click.echo(f"Pattern not found: {pattern}")
        return

    excluded_dirs = [p for p in excluded_dirs if p != pattern]
    current_config.setdefault("indexing", {})["EXCLUDED_DIRS"] = excluded_dirs
    save_config(current_config)
    import filesift._config.config as config_module
    config_module.config_dict = load_config()

    click.echo(f"Removed ignore pattern: {pattern}")


@config.command("list-ignore")
def list_ignore():
    """List all ignore patterns"""
    from filesift._config.config import load_config

    current_config = load_config()
    excluded_dirs = current_config.get("indexing", {}).get("EXCLUDED_DIRS", [])

    click.echo("Current ignore patterns:")
    if not excluded_dirs:
        click.echo("  (none)")
        return

    for pattern in excluded_dirs:
        click.echo(f"  {pattern}")


@config.command()
def path():
    """Show the path to the configuration file"""
    from platformdirs import user_config_dir
    from pathlib import Path

    config_dir = Path(user_config_dir("filesift"))
    config_file = config_dir / "config.toml"

    click.echo(str(config_file))


@cli.group()
def daemon():
    """Manage the filesift daemon"""
    pass


@daemon.command()
def start():
    """Start the filesift daemon"""
    from filesift.cli.daemon_utils import is_daemon_running, start_daemon_process, get_daemon_pid, get_daemon_url

    if is_daemon_running():
        pid = get_daemon_pid()
        url = get_daemon_url()
        click.echo(f"Daemon is already running (PID: {pid}, URL: {url})")
        return

    if start_daemon_process():
        import time
        time.sleep(0.5)
        if is_daemon_running():
            pid = get_daemon_pid()
            url = get_daemon_url()
            click.echo(f"Daemon started successfully (PID: {pid}, URL: {url})")
        else:
            click.echo("Daemon process started but not responding. Check logs.")
    else:
        click.echo("Failed to start daemon.", err=True)


@daemon.command()
def stop():
    """Stop the filesift daemon"""
    from filesift.cli.daemon_utils import is_daemon_running, get_daemon_pid, DAEMON_PID_FILE
    import os
    import signal

    if not is_daemon_running():
        click.echo("Daemon is not running.")
        if DAEMON_PID_FILE.exists():
            DAEMON_PID_FILE.unlink()
        return

    pid = get_daemon_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            click.echo(f"Sent termination signal to daemon (PID: {pid})")
            import time
            time.sleep(0.5)
            if not is_daemon_running():
                DAEMON_PID_FILE.unlink()
                click.echo("Daemon stopped successfully.")
            else:
                click.echo("Daemon did not stop, trying SIGKILL...")
                try:
                    os.kill(pid, signal.SIGKILL)
                    DAEMON_PID_FILE.unlink()
                    click.echo("Daemon force-killed.")
                except ProcessLookupError:
                    click.echo("Daemon already stopped.")
        except ProcessLookupError:
            click.echo(f"Daemon process (PID: {pid}) not found. Cleaning up PID file.")
            DAEMON_PID_FILE.unlink()
        except PermissionError:
            click.echo(f"Permission denied. Try: kill {pid}", err=True)
    else:
        click.echo("Could not find daemon PID.")


@daemon.command()
def status():
    """Check daemon status"""
    from filesift.cli.daemon_utils import is_daemon_running, get_daemon_url, get_daemon_pid
    from filesift._config.config import config_dict

    if is_daemon_running():
        url = get_daemon_url()
        pid = get_daemon_pid()
        daemon_config = config_dict.get("daemon", {})
        timeout = daemon_config.get("INACTIVITY_TIMEOUT", 300)
        click.echo(f"Daemon is running")
        click.echo(f"  PID: {pid}")
        click.echo(f"  URL: {url}")
        
        try:
            import requests # ensure requests is available
            status_resp = requests.get(f"{url}/status", timeout=5)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                loaded = status_data.get("loaded", [])
                loading = status_data.get("loading", [])
                
                if loaded:
                    click.echo(f"  Loaded Indexes ({len(loaded)}):")
                    for p in loaded:
                        click.echo(f"    - {p}")
                
                if loading:
                    click.echo(f"  Loading in Background ({len(loading)}):")
                    for p in loading:
                        click.echo(f"    - {p}")
                elif not loaded:
                    click.echo("  No indexes loaded.")
        except Exception:
            pass

        if timeout > 0:
            click.echo(f"  Auto-shutdown: after {timeout}s of inactivity")
        else:
            click.echo(f"  Auto-shutdown: disabled")
    else:
        click.echo("Daemon is not running.")


@daemon.command("list")
def list_daemons():
    """List all running filesift daemon processes"""
    import subprocess
    import os

    current_pid = os.getpid()
    click.echo("Searching for filesift daemon processes...")
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        lines = result.stdout.split('\n')
        daemon_processes = []
        for line in lines:
            if 'daemon_main.py' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        if pid != current_pid:
                            daemon_processes.append(line)
                    except (ValueError, IndexError):
                        daemon_processes.append(line)

        if daemon_processes:
            click.echo("\nFound daemon processes:")
            for proc in daemon_processes:
                click.echo(f"  {proc}")
        else:
            click.echo("No daemon processes found.")
    except Exception as e:
        click.echo(f"Error listing processes: {e}", err=True)
        click.echo("\nManual command:")
        click.echo("  ps aux | grep daemon_main.py")


@daemon.command("kill")
@click.option("--pid", type=int, help="Kill daemon by PID")
@click.option("--all", is_flag=True, help="Kill all filesift daemon processes")
def kill_daemon(pid: Optional[int], all: bool):
    """Kill daemon process(es)"""
    import os
    import signal
    import subprocess
    import sys
    from filesift.cli.daemon_utils import get_daemon_pid, DAEMON_PID_FILE

    if all:
        click.echo("Killing all filesift daemon processes...")
        try:
            if sys.platform.startswith("win"):
                tasklist = subprocess.run(
                    ["wmic", "process", "where", "CommandLine like '%daemon_main.py%'", "get", "ProcessId,CommandLine", "/FORMAT:csv"],
                    capture_output=True, text=True
                )
                killed = 0
                for line in tasklist.stdout.splitlines():
                    if "daemon_main.py" in line:
                        columns = line.strip().split(",")
                        if len(columns) >= 2:
                            pid = columns[-1]
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                                killed += 1
                            except Exception:
                                pass
                click.echo(f"Attempted to kill {killed} daemon process(es) on Windows.")
            else:
                subprocess.run(["pkill", "-f", "daemon_main.py"], check=False)
                click.echo("Killed all daemon processes.")
            if DAEMON_PID_FILE.exists():
                DAEMON_PID_FILE.unlink()
        except Exception as e:
            click.echo(f"Error killing processes: {e}", err=True)
    elif pid:
        try:
            os.kill(pid, signal.SIGTERM)
            click.echo(f"Sent termination signal to PID {pid}")
            import time
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
                click.echo(f"Force-killed PID {pid}")
            except ProcessLookupError:
                click.echo(f"Process {pid} terminated.")
        except ProcessLookupError:
            click.echo(f"Process {pid} not found.")
        except PermissionError:
            click.echo(f"Permission denied. Try: kill {pid}", err=True)
    else:
        from filesift.cli.daemon_utils import is_daemon_running
        if not is_daemon_running():
            click.echo("Daemon is not running.")
            return

        registered_pid = get_daemon_pid()
        if registered_pid:
            try:
                os.kill(registered_pid, signal.SIGTERM)
                click.echo(f"Sent termination signal to daemon (PID: {registered_pid})")
                import time
                time.sleep(0.5)
                if not is_daemon_running():
                    DAEMON_PID_FILE.unlink()
                    click.echo("Daemon stopped.")
                else:
                    os.kill(registered_pid, signal.SIGKILL)
                    DAEMON_PID_FILE.unlink()
                    click.echo("Daemon force-killed.")
            except ProcessLookupError:
                click.echo("Daemon process not found. Cleaning up PID file.")
                DAEMON_PID_FILE.unlink()
            except PermissionError:
                click.echo(f"Permission denied. Try: kill {registered_pid}", err=True)
        else:
            click.echo("No registered daemon PID found.")


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()
