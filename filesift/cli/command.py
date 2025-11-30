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
    # Determine the directory to search in
    if path:
        search_dir = Path(path)
    else:
        search_dir = Path.cwd()
    
    index_dir = search_dir / ".filesift"
    
    # Check if index exists
    if not index_dir.exists() or not any(index_dir.iterdir()):
        click.echo(f"Error: No index found in {search_dir}", err=True)
        click.echo(f"\nTo create an index, run:", err=True)
        click.echo(f"  filesift index {search_dir}", err=True)
        raise click.Abort()
    
    try:
        from filesift._core.query import QueryDriver
    except ImportError:
        click.echo("Error: Couldn't load QueryDriver. Aborting...", err=True)
        raise click.Abort()
    
    try:
        # Load the index
        print("Loading index...")
        query_driver = QueryDriver()
        query_driver.load_from_disk(str(index_dir))
        
        # Perform hybrid search
        click.echo(f"Searching for: {query}")
        results = query_driver.search(query)
        
        # Display results
        if not results:
            click.echo("No results found.")
            return
        
        click.echo(f"\nFound {len(results)} result(s):\n")
        for i, result in enumerate(results, 1):
            # Format the result nicely
            click.echo(f"{i}. {result.path}")
            
            # Show relevant metadata if available
            metadata_parts = []
            if result.metadata.get("file_type"):
                metadata_parts.append(f"Type: {result.metadata['file_type']}")
            
            if metadata_parts:
                click.echo(f"   {' | '.join(metadata_parts)}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error during search: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--reindex", is_flag=True, help="Force a complete reindex, overwriting any existing index")
def index(path: Path, reindex: bool):
    """Index a directory for search"""
    index_dir = path / ".filesift"
    
    try:
        from filesift._core.indexer import Indexer
    except ImportError:
        print("Couldn't load indexer. Aborting...")
        raise click.Abort()
    
    try:
        # Create Indexer instance
        indexer = Indexer(root=path)

        existing_index = index_dir.exists() and any(index_dir.iterdir())
        
        # Load existing index if present (unless reindex is requested)
        if existing_index and not reindex:
            try:
                indexer.load(index_dir)
                click.echo("Existing index found, will check for changes...")
            except Exception as e:
                click.echo(f"Warning: Could not load existing index: {e}", err=True)
                click.echo("Starting fresh index.")
        elif existing_index and reindex:
            click.echo("Reindexing: creating fresh index (existing index will be overwritten)...")
        
        # Run index() method
        indexer.index()
        
        # Save index to .filesift directory
        indexer.save(index_dir)

        if reindex:
            click.echo("Index successfully reindexed.")
        elif existing_index:
            click.echo("Index successfully updated.")
        else:
            click.echo(f"Index successfully created.")
        
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
    """Set a configuration value"""
    # TODO: Implement config set
    # - Validate key exists in settings
    # - Parse and validate value type
    # - Update settings (may need to persist to file)
    click.echo(f"Setting {key} = {value}")
    pass


@config.command("add-ignore")
@click.option("-f", "--file", "file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Add ignore patterns from a file (similar to .gitignore)")
@click.argument("patterns", nargs=-1, required=False)
def add_ignore(file_path: Optional[Path], patterns: tuple):
    """Add ignore patterns"""
    # TODO: Implement add-ignore
    # - If --file is provided, read patterns from file (one per line)
    # - Otherwise, use patterns from command line
    # - Add patterns to settings.EXCLUDED_DIRS or a separate ignore list
    # - Persist to configuration file
    if file_path:
        click.echo(f"Adding ignore patterns from file: {file_path}")
        # TODO: Read patterns from file
    if patterns:
        click.echo(f"Adding ignore patterns: {patterns}")
    if not file_path and not patterns:
        click.echo("Error: Must provide either --file or patterns", err=True)
        return
    pass


@config.command("remove-ignore")
@click.argument("pattern", required=True)
def remove_ignore(pattern: str):
    """Remove an ignore pattern"""
    # TODO: Implement remove-ignore
    # - Remove pattern from settings.EXCLUDED_DIRS or ignore list
    # - Persist to configuration file
    click.echo(f"Removing ignore pattern: {pattern}")
    pass


@config.command("list-ignore")
def list_ignore():
    """List all ignore patterns"""
    # TODO: Implement list-ignore
    # - Display all current ignore patterns
    # - May need to read from settings or config file
    click.echo("Current ignore patterns:")
    # TODO: Display patterns
    pass


@config.command()
def path():
    """Show the path to the configuration file"""
    # TODO: Implement path
    # - Determine config file location (e.g., ~/.filesift/config.json or project-specific)
    # - Display the path
    click.echo("Configuration file path:")
    # TODO: Display path
    pass


def main():
    """Entry point for the CLI"""
    cli()