import os
# Set TOKENIZERS_PARALLELISM before any tokenizers are loaded to avoid fork warnings
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import click
from pathlib import Path
from typing import Optional


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """FileSift - Intelligent file indexing and search system"""
    pass


@cli.command()
@click.argument("query", required=True)
@click.option("--path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
              help="Directory to search in (defaults to current directory)")
def find(query: str, path: Optional[Path]):
    """Search for files using a query string"""
    if path:
        search_dir = Path(path)
    else:
        search_dir = Path.cwd()
    
    index_dir = search_dir / ".filesift"
    
    if not index_dir.exists() or not any(index_dir.iterdir()):
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
                SearchResult(
                    path=r["path"],
                    score=r["score"],
                    metadata=r["metadata"]
                )
                for r in data["results"]
            ]
            
            if not results:
                click.echo("No results found.")
                return
            
            click.echo(f"\nFound {len(results)} result(s):\n")
            for i, result in enumerate(results, 1):
                click.echo(f"{i}. {result.path}")
                
                metadata_parts = []
                if result.metadata.get("file_type"):
                    metadata_parts.append(f"Type: {result.metadata['file_type']}")
                
                if metadata_parts:
                    click.echo(f"   {' | '.join(metadata_parts)}")
                click.echo()
            return
        except Exception as e:
            click.echo(f"Error communicating with daemon: {e}", err=True)
            click.echo("Falling back to local QueryDriver...", err=True)
    
    try:
        from filesift._core.query import QueryDriver
    except ImportError:
        click.echo("Error: Couldn't load QueryDriver. Aborting...", err=True)
        raise click.Abort()
    
    try:
        print("Loading index...")
        query_driver = QueryDriver()
        query_driver.load_from_disk(str(index_dir))
        
        click.echo(f"Searching for: {query}")
        results = query_driver.search(query)
        
        if not results:
            click.echo("No results found.")
            return
        
        click.echo(f"\nFound {len(results)} result(s):\n")
        for i, result in enumerate(results, 1):
            click.echo(f"{i}. {result.path}")
            
            metadata_parts = []
            if result.metadata.get("file_type"):
                metadata_parts.append(f"Type: {result.metadata['file_type']}")
            
            if metadata_parts:
                click.echo(f"   {' | '.join(metadata_parts)}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error during search: {e}", err=True)
        raise click.Abort()


def _validate_llm_config():
    """Validate that required LLM configuration is set"""
    from filesift._config.config import config_dict
    
    llm_config = config_dict.get("llm", {})
    models_config = config_dict.get("models", {})
    
    llm_api_key = llm_config.get("LLM_API_KEY", "")
    llm_base_url = llm_config.get("LLM_BASE_URL", "")
    main_model = models_config.get("MAIN_MODEL", "")
    
    issues = []
    
    # Check API key
    if not llm_api_key or llm_api_key == "placeholder_key":
        issues.append("LLM_API_KEY is not set or is still the default placeholder")
    
    # Check main model
    if not main_model:
        issues.append("MAIN_MODEL is not set")
    
    # Check base URL format if provided (basic validation)
    if llm_base_url and llm_base_url.strip():
        if not (llm_base_url.startswith("http://") or llm_base_url.startswith("https://")):
            issues.append("LLM_BASE_URL should start with http:// or https://")
    
    if issues:
        click.echo("Error: LLM configuration is incomplete or invalid:", err=True)
        click.echo("", err=True)
        for issue in issues:
            click.echo(f"  • {issue}", err=True)
        click.echo("", err=True)
        click.echo("Please configure your LLM settings using the 'config' subcommand:", err=True)
        click.echo("", err=True)
        click.echo("  For OpenAI (cloud):", err=True)
        click.echo("    filesift config set llm.LLM_BASE_URL \"\"", err=True)
        click.echo("    filesift config set llm.LLM_API_KEY \"sk-your-openai-api-key\"", err=True)
        click.echo("    filesift config set models.MAIN_MODEL \"gpt-4o-mini\"", err=True)
        click.echo("", err=True)
        click.echo("  For LM Studio (local):", err=True)
        click.echo("    filesift config set llm.LLM_BASE_URL \"http://localhost:1234/v1\"", err=True)
        click.echo("    filesift config set llm.LLM_API_KEY \"lm-studio\"", err=True)
        click.echo("    filesift config set models.MAIN_MODEL \"your-model-name\"", err=True)
        click.echo("", err=True)
        click.echo("  For Ollama (local):", err=True)
        click.echo("    filesift config set llm.LLM_BASE_URL \"http://localhost:11434/v1\"", err=True)
        click.echo("    filesift config set llm.LLM_API_KEY \"ollama\"", err=True)
        click.echo("    filesift config set models.MAIN_MODEL \"llama3.2\"", err=True)
        click.echo("", err=True)
        click.echo("See 'filesift config list llm' and 'filesift config list models' for current values.", err=True)
        return False
    
    return True


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--reindex", is_flag=True, help="Force a complete reindex, overwriting any existing index")
def index(path: Path, reindex: bool):
    """Index a directory for search"""
    # Validate LLM configuration before proceeding
    if not _validate_llm_config():
        raise click.Abort()
    
    index_dir = path / ".filesift"
    
    try:
        from filesift._core.indexer import Indexer
    except ImportError:
        print("Couldn't load indexer. Aborting...")
        raise click.Abort()
    
    try:
        indexer = Indexer(root=path)

        existing_index = index_dir.exists() and any(index_dir.iterdir())
        
        if existing_index and not reindex:
            try:
                indexer.load(index_dir)
                click.echo("Existing index found, will check for changes...")
            except Exception as e:
                click.echo(f"Warning: Could not load existing index: {e}", err=True)
                click.echo("Starting fresh index.")
        elif existing_index and reindex:
            click.echo("Reindexing: creating fresh index (existing index will be overwritten)...")
        
        indexer.index()
        
        indexer.save(index_dir)

        if reindex:
            click.echo("Index successfully reindexed.")
        elif existing_index:
            click.echo("Index successfully updated.")
        else:
            click.echo(f"Index successfully created.")
        
        from filesift.cli.daemon_utils import ensure_daemon_running, get_daemon_url
        import requests
        
        if ensure_daemon_running():
            try:
                url = get_daemon_url()
                requests.post(
                    f"{url}/reload",
                    json={"index_path": str(index_dir)},
                    timeout=5
                )
            except Exception as e:
                click.echo(f"Warning: Could not reload index in daemon: {e}", err=True)
        else:
            click.echo("Warning: Could not start daemon.", err=True)
        
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
        """Format a value for display"""
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
            if section_name in current_config:
                section_config = current_config[section_name]
            else:
                section_config = default_config[section_name]
            
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
        if section in current_config:
            section_config = current_config[section]
        else:
            section_config = default_config[section]
        
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
    from filesift._config.config import load_config, save_config, config_dict

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
    import sys
    import os
    
    current_pid = os.getpid()
    click.echo("Searching for filesift daemon processes...")
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
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
        click.echo("  or")
        click.echo("  ps aux | grep filesift")


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