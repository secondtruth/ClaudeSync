import click
from typing import List, Dict, Optional

class ProjectSelector:
    """Interactive project selection utilities."""
    
    @staticmethod
    def select_multiple(projects: List[Dict], 
                       prompt: str = "Select projects",
                       show_all: bool = True) -> List[Dict]:
        """Interactive multi-select for projects."""
        if not projects:
            return []
        
        # Display projects
        click.echo(f"\n{prompt}:")
        click.echo("(Use space to select/deselect, Enter to confirm, 'a' to select all, 'n' to select none)\n")
        
        # Initialize selection state
        selected = [False] * len(projects)
        current_index = 0
        
        def display_projects():
            """Display projects with selection state."""
            click.clear()
            click.echo(f"\n{prompt}:\n")
            
            for i, project in enumerate(projects):
                prefix = "→ " if i == current_index else "  "
                check = "[✓]" if selected[i] else "[ ]"
                status = " (Archived)" if project.get('archived_at') else ""
                
                # Highlight current line
                if i == current_index:
                    click.echo(click.style(
                        f"{prefix}{check} {project['name']} (ID: {project['id']}){status}",
                        fg='cyan'
                    ))
                else:
                    click.echo(f"{prefix}{check} {project['name']} (ID: {project['id']}){status}")
            
            click.echo("\n[Space: toggle, ↑↓: navigate, Enter: confirm, a: all, n: none, q: quit]")
        
        # Interactive selection loop
        while True:
            display_projects()
            
            # Get single keypress
            key = click.getchar()
            
            if key == ' ':  # Space - toggle selection
                selected[current_index] = not selected[current_index]
            elif key == '\r' or key == '\n':  # Enter - confirm
                break
            elif key == 'a' or key == 'A':  # Select all
                selected = [True] * len(projects)
            elif key == 'n' or key == 'N':  # Select none
                selected = [False] * len(projects)
            elif key == 'q' or key == 'Q':  # Quit
                return []
            elif key == '\x1b':  # Escape sequence (arrow keys)
                next_key = click.getchar()
                if next_key == '[':
                    arrow = click.getchar()
                    if arrow == 'A':  # Up arrow
                        current_index = max(0, current_index - 1)
                    elif arrow == 'B':  # Down arrow
                        current_index = min(len(projects) - 1, current_index + 1)
        
        # Return selected projects
        return [p for i, p in enumerate(projects) if selected[i]]
    
    @staticmethod
    def select_single(projects: List[Dict], 
                     prompt: str = "Select a project") -> Optional[Dict]:
        """Interactive single project selection."""
        if not projects:
            return None
        
        click.echo(f"\n{prompt}:")
        
        for i, project in enumerate(projects, 1):
            status = " (Archived)" if project.get('archived_at') else ""
            click.echo(f"  {i}. {project['name']} (ID: {project['id']}){status}")
        
        while True:
            try:
                selection = click.prompt("\nEnter number (or 'q' to quit)", type=str)
                if selection.lower() == 'q':
                    return None
                
                index = int(selection) - 1
                if 0 <= index < len(projects):
                    return projects[index]
                else:
                    click.echo("Invalid selection. Please try again.")
            except ValueError:
                click.echo("Please enter a number or 'q' to quit.")
    
    @staticmethod
    def filter_projects(projects: List[Dict], 
                       search_term: str = None,
                       include_archived: bool = False) -> List[Dict]:
        """Filter projects based on criteria."""
        filtered = projects
        
        # Filter archived
        if not include_archived:
            filtered = [p for p in filtered if not p.get('archived_at')]
        
        # Filter by search term
        if search_term:
            search_lower = search_term.lower()
            filtered = [p for p in filtered 
                       if search_lower in p['name'].lower() 
                       or search_lower in p['id'].lower()]
        
        return filtered