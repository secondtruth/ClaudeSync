import click
import datetime

from claudesync.provider_factory import get_provider
from ..exceptions import ProviderError
from ..utils import handle_errors


@click.group()
def auth():
    """Manage authentication."""
    pass


@auth.command()
@click.option(
    "--provider",
    prompt="Choose provider",
    type=click.Choice(["claude.ai"], case_sensitive=False),
    default="claude.ai",
    help="The provider to use for this project",
)
@click.option(
    "--session-key",
    help="Directly provide the Claude.ai session key",
    envvar="CLAUDE_SESSION_KEY",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Automatically approve the suggested expiry time",
)
@click.pass_context
@handle_errors
def login(ctx, provider, session_key, auto_approve):
    """Authenticate with an AI provider."""
    config = ctx.obj
    provider_instance = get_provider(config, provider)
    
    # Suggest quick auth if no session key provided
    if not session_key:
        click.echo("\n💡 Tip: Try 'csync auth quick' for easier authentication with a bookmarklet!\n")

    try:
        if session_key:
            # If session key is provided, bypass the interactive prompt
            if not session_key.startswith("sk-ant"):
                raise ProviderError(
                    "Invalid sessionKey format. Must start with 'sk-ant'"
                )
            # Set auto_approve to True when session key is provided
            provider_instance._auto_approve_expiry = auto_approve
            provider_instance._provided_session_key = session_key

        session_key, expiry = provider_instance.login()
        config.set_session_key(provider, session_key, expiry)
        click.echo(
            f"Successfully authenticated with {provider}. Session key stored globally."
        )
    except ProviderError as e:
        click.echo(f"Authentication failed: {str(e)}")


@auth.command()
@click.pass_obj
def logout(config):
    """Log out from all AI providers."""
    config.clear_all_session_keys()
    click.echo("Logged out from all providers successfully.")


@auth.command()
@click.pass_obj
def ls(config):
    """List all authenticated providers."""
    authenticated_providers = config.get_providers_with_session_keys()
    if authenticated_providers:
        click.echo("Authenticated providers:")
        for provider in authenticated_providers:
            click.echo(f"  - {provider}")
    else:
        click.echo("No authenticated providers found.")


@auth.command()
@click.option('--browser', type=click.Choice(['playwright', 'selenium']), 
              default='playwright', help='Browser automation method')
@click.option('--headless', is_flag=True, help='Run browser in headless mode (playwright only)')
@click.pass_context
@handle_errors
def browser_login(ctx, browser, headless):
    """Authenticate using browser automation to grab session key."""
    import datetime
    from ..browser_auth import BrowserAuth
    
    click.echo(f"Starting browser automation with {browser}...")
    
    try:
        if browser == 'selenium':
            if headless:
                click.echo("Warning: Selenium doesn't support headless mode for auth")
            session_key = BrowserAuth.get_session_key_selenium()
        else:
            session_key = BrowserAuth.get_session_key_playwright(headless=headless)
        
        if session_key:
            # Get expiry (30 days from now)
            expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
            
            # Save session key
            config = ctx.obj
            provider_instance = get_provider(config, 'claude.ai')
            config.set_session_key('claude.ai', session_key, expires)
            
            click.echo(f"✓ Successfully authenticated! Session key retrieved and stored.")
            
            # Test by getting organizations
            try:
                orgs = provider_instance.get_organizations()
                if orgs:
                    click.echo(f"✓ Verified access to {len(orgs)} organization(s)")
            except Exception as e:
                click.echo(f"⚠ Warning: Could not verify organizations: {e}")
        else:
            click.echo("Failed to retrieve session key from browser")
            
    except Exception as e:
        click.echo(f"✗ Browser authentication failed: {str(e)}")
        if not headless:
            click.echo("\nFalling back to manual login...")
            ctx.invoke(login)


@auth.command()
@click.pass_context
@handle_errors
def quick(ctx):
    """Quick authentication using bookmarklet or console method (no browser automation needed)."""
    from ..auth_helper import SimpleAuthHelper
    
    session_key = SimpleAuthHelper.quick_auth()
    
    if session_key:
        # Get expiry (30 days from now)
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        
        # Save session key
        config = ctx.obj
        config.set_session_key('claude.ai', session_key, expires)
        
        click.echo(click.style("\n✓ Successfully authenticated with Claude.ai!", fg='green', bold=True))
        
@auth.command()
@click.pass_context
@handle_errors  
def refresh(ctx):
    """Refresh authentication session without full re-login."""
    config = ctx.obj
    
    # Check for existing session key
    session_key = config.get_session_key('claude.ai')
    if not session_key:
        click.echo("No active session found. Please run 'csync auth login' first.")
        return
        
    # Try to refresh by testing the session
    provider_instance = get_provider(config, 'claude.ai')
    
    try:
        # Test the session by getting organizations
        orgs = provider_instance.get_organizations()
        
        # Update expiry to 30 days from now
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        config.set_session_key('claude.ai', session_key, expires)
        
        click.echo(f"✓ Session refreshed successfully!")
        if orgs:
            click.echo(f"✓ Access verified to {len(orgs)} organization(s)")
            
    except Exception as e:
        click.echo(f"✗ Session refresh failed: {str(e)}")
        click.echo("\nSession may have expired. Please run 'csync auth login' to re-authenticate.")
        
        # Test by getting organizations
        try:
            provider = get_provider(config, 'claude.ai')
            orgs = provider.get_organizations()
            if orgs:
                click.echo(f"✓ Verified access to {len(orgs)} organization(s)")
                
                # Offer to set organization
                if len(orgs) == 1:
                    org = orgs[0]
                    if click.confirm(f"\nSet '{org['name']}' as active organization?"):
                        config.set('active_organization_id', org['id'])
                        config.set('active_organization_name', org['name'])
                        click.echo(f"✓ Active organization set to: {org['name']}")
                        
        except Exception as e:
            click.echo(f"⚠ Warning: Could not verify organizations: {e}")
    else:
        click.echo(click.style("\n✗ Authentication failed", fg='red'))
        click.echo("Please try again or use 'csync auth login' for manual entry")
