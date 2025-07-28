import json
import os
from colorthief import ColorThief
from PIL import Image

def is_color_lighter(color1, color2):
    """
    Determine which color is lighter by calculating relative luminance.
    Returns True if color1 is lighter than color2.
    """
    def get_luminance(color):
        # Convert hex to RGB
        if color.startswith('#'):
            color = color[1:]
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        
        # Calculate relative luminance using sRGB coefficients
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    return get_luminance(color1) > get_luminance(color2)

def get_team_colors(team_number):
    """Extract dominant colors from team avatar."""
    # Use bbot.png for team numbers 9970-9999
    if 9970 <= team_number <= 9999:
        avatar_path = "assets/avatars/bbot.png"
    else:
        avatar_path = f"assets/avatars/{team_number}.png"
    
    if not os.path.exists(avatar_path):
        # Try stock.png as fallback
        stock_path = "assets/avatars/stock.png"
        if os.path.exists(stock_path):
            try:
                color_thief = ColorThief(stock_path)
                dominant_colors = color_thief.get_palette(color_count=2, quality=1)
                if len(dominant_colors) >= 2:
                    colors = [f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}" for color in dominant_colors[:2]]
                    # Ensure darker color comes first
                    if is_color_lighter(colors[0], colors[1]):
                        colors = colors[::-1]
                    return colors
                elif len(dominant_colors) == 1:
                    color = dominant_colors[0]
                    hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                    return [hex_color, hex_color]
            except Exception:
                pass
        # Final fallback colors
        return ["#1e3a8a", "#3b82f6"]  # Blue gradient
    
    try:
        color_thief = ColorThief(avatar_path)
        # Get the 2 most dominant colors
        dominant_colors = color_thief.get_palette(color_count=2, quality=1)
        
        # Ensure we have exactly 2 colors
        if len(dominant_colors) >= 2:
            colors = [f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}" for color in dominant_colors[:2]]
            # Ensure darker color comes first
            if is_color_lighter(colors[0], colors[1]):
                colors = colors[::-1]
            return colors
        elif len(dominant_colors) == 1:
            # If only one color, duplicate it
            color = dominant_colors[0]
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            return [hex_color, hex_color]
        else:
            # Fallback if no colors extracted - try stock.png
            stock_path = "assets/avatars/stock.png"
            if os.path.exists(stock_path):
                try:
                    color_thief = ColorThief(stock_path)
                    dominant_colors = color_thief.get_palette(color_count=2, quality=1)
                    if len(dominant_colors) >= 2:
                        colors = [f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}" for color in dominant_colors[:2]]
                        # Ensure darker color comes first
                        if is_color_lighter(colors[0], colors[1]):
                            colors = colors[::-1]
                        return colors
                    elif len(dominant_colors) == 1:
                        color = dominant_colors[0]
                        hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                        return [hex_color, hex_color]
                except Exception:
                    pass
            # Final fallback colors
            return ["#1e3a8a", "#3b82f6"]
    except Exception as e:
        print(f"Error extracting colors for team {team_number}: {e}")
        # Fallback colors if extraction fails
        return ["#1e3a8a", "#3b82f6"]

def generate_team_colors():
    """Generate colors for all teams and save to JSON."""
    # Load team data to get all team numbers
    with open("data/teams.json", "r", encoding="utf-8") as f:
        team_data = json.load(f)
    
    team_colors = {}
    total_teams = len(team_data)
    
    print(f"Processing {total_teams} teams...")
    
    for i, (team_number_str, team_info) in enumerate(team_data.items()):
        try:
            team_number = int(team_number_str)
        except ValueError:
            continue
            
        colors = get_team_colors(team_number)
        team_colors[team_number_str] = {
            "primary": colors[0],
            "secondary": colors[1]
        }
        
        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{total_teams} teams...")
    
    # Save to JSON file
    with open("team_colors.json", "w", encoding="utf-8") as f:
        json.dump(team_colors, f, indent=2)
    
    print(f"Generated colors for {len(team_colors)} teams and saved to team_colors.json")

if __name__ == "__main__":
    generate_team_colors() 